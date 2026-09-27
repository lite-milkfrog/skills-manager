from pathlib import Path

ROOT = Path(__file__).parents[1]
DESKTOP = ROOT / "scripts" / "desktop"


def test_m08_manager_is_loopback_only_on_dedicated_port() -> None:
    server = (DESKTOP / "manager-server.cmd").read_text(encoding="utf-8")
    ensure = (DESKTOP / "ensure-manager.ps1").read_text(encoding="utf-8")
    assert "--host 127.0.0.1 --port 8955" in server
    assert "http://127.0.0.1:8955/api/health" in ensure
    assert "Refusing to kill or replace" in ensure


def test_m08_shortcut_opens_independent_manager_after_ensure() -> None:
    opener = (DESKTOP / "open-manager.ps1").read_text(encoding="utf-8")
    installer = (DESKTOP / "install-integration.ps1").read_text(encoding="utf-8")
    assert "ensure-manager.ps1" in opener
    assert 'Start-Process "http://127.0.0.1:8955/"' in opener
    assert "Skill Control Plane.lnk" in installer
    assert "local-prestart.cmd" in installer
    assert "Skill Control Plane integration BEGIN" in installer
    assert "local-launcher-overlay.cmd" not in installer
