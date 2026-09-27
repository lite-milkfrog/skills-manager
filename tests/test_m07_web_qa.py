from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

from skill_control_plane.manager import ManagerBackend
from skill_control_plane.web_manager import create_server


def test_m07_sources_page_is_bounded(seeded) -> None:
    manager = ManagerBackend(
        seeded["registry"],
        seeded["db"].path,
        explorer_opener=lambda _path: None,
    )
    all_sources = manager.sources_list()
    page = manager.sources_page(limit=1)
    assert page["total"] == len(all_sources)
    assert len(page["items"]) <= 1
    if len(all_sources) > 1:
        assert page["next_cursor"] == 1


def test_m07_sources_page_http_and_accessibility_shell(seeded) -> None:
    web_root = Path(__file__).resolve().parents[1] / "web" / "manager"
    server = create_server(
        "127.0.0.1",
        0,
        registry=seeded["registry"],
        db_path=seeded["db"].path,
        web_root=web_root,
        explorer_opener=lambda _path: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/api/sources-page?limit=1", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert "items" in payload
        assert "total" in payload
        assert len(payload["items"]) <= 1

        with urllib.request.urlopen(base + "/", timeout=2) as response:
            html = response.read().decode("utf-8")
        assert 'class="skip-link"' in html
        assert 'name="theme-color"' in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_m07_frontend_contains_accessible_dynamic_controls() -> None:
    web_root = Path(__file__).resolve().parents[1] / "web" / "manager"
    app = (web_root / "app.js").read_text(encoding="utf-8")
    css = (web_root / "styles.css").read_text(encoding="utf-8")

    assert 'for="runStatus"' in app
    assert 'for="runWorkflow"' in app
    assert 'for="stage-key-' in app
    assert 'name="stage-key-' in app
    assert 'aria-label="Binding type"' in app
    assert "sources-page?cursor=" in app
    assert ".skip-link:focus-visible" in css
    assert "min-height: 44px" in css
