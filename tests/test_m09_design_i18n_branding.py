from __future__ import annotations

import struct
import threading
import urllib.request
from pathlib import Path

from skill_control_plane.web_manager import create_server

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "manager"
DESKTOP = ROOT / "scripts" / "desktop"


def test_m09_i18n_is_single_frontend_with_zh_cn_default() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert '<html lang="zh-CN">' in index
    assert 'src="/i18n.js"' in index
    assert 'id="localeZh"' in index
    assert 'id="localeEn"' in index
    assert "scp.locale" in i18n
    assert "DEFAULT_LOCALE = 'zh-CN'" in i18n
    assert "document.documentElement.lang = locale" in i18n
    assert "localStorage.setItem(i18n.STORAGE_KEY, locale)" in app
    assert "await render()" in app
    assert not (WEB / "index.zh-CN.html").exists()
    assert not (WEB / "index.en.html").exists()
    assert not (WEB / "app.zh-CN.js").exists()
    assert not (WEB / "app.en.js").exists()


def test_m09_static_assets_revalidate_after_local_update(seeded) -> None:
    server = create_server(
        "127.0.0.1",
        0,
        registry=seeded["registry"],
        db_path=seeded["db"].path,
        web_root=WEB,
        explorer_opener=lambda _path: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/", timeout=2) as response:
            assert "no-cache" in response.headers["Cache-Control"]
            html = response.read().decode("utf-8")
        assert 'data-i18n="Home"' in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_m09_branding_assets_and_shortcut_contract() -> None:
    svg = WEB / "assets" / "skill-control-plane-mark.svg"
    ico = WEB / "assets" / "skill-control-plane.ico"
    installer = (DESKTOP / "install-integration.ps1").read_text(encoding="utf-8")

    assert svg.is_file()
    assert ico.is_file()
    source = svg.read_text(encoding="utf-8")
    assert "Skill Control Plane" in source
    assert "three connected orchestration nodes" in source

    reserved, icon_type, count = struct.unpack("<HHH", ico.read_bytes()[:6])
    assert (reserved, icon_type) == (0, 1)
    assert count == 7

    # The final consolidation retires the second runtime-starting Desktop
    # entry, but preserves a frontend-only Internet shortcut. WAC remains the
    # only lifecycle owner; the Skills shortcut only opens the 8955 UI.
    assert 'skill-control-plane.ico' in installer
    assert '$shortcut.IconLocation = "$Icon,0"' not in installer
    assert "SHELL32.dll,220" not in installer
    assert 'external-ensure' in installer
    assert 'skills-control-plane.json' in installer
    assert 'Skills Manager.url' in installer
    assert 'URL=http://127.0.0.1:8955/' in installer
    assert 'frontend_shortcut_mode = "open-only"' in installer
    assert 'legacy_shortcut' in installer
    assert 'retired-owned' in installer


def test_m09_design_system_records_primary_harness_and_user_reboot_boundary() -> None:
    design = (ROOT / "design" / "M09-DESIGN.md").read_text(encoding="utf-8")
    assert "**PRIMARY: Impeccable**" in design
    assert "webapp-testing" in design
    assert "accessibility-review" in design
    assert "design-qa" in design and "NOT USED" in design
    assert "USER_MANUAL_REBOOT_ACCEPTANCE = PENDING_USER" in design
