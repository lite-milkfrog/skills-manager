from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "manager"


def test_m12_workflow_agent_prompt_has_programmatic_label() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert '<label class="sr-only" for="' in app
    assert "' + esc(textareaId) + '" in app
    assert '">Agent prompt</label>' in app


def test_m12_mobile_primary_icon_controls_keep_44px_touch_targets() -> None:
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert (
        ".nav-toggle { width: 44px; min-width: 44px; }"
        in styles
    )
    expected = (
        ".step-actions .icon-button { width: 44px; min-width: 44px; "
        "height: 44px; min-height: 44px; }"
    )
    assert expected in styles
