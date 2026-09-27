from pathlib import Path

ROOT = Path(__file__).parents[1]
DESKTOP = ROOT / "scripts" / "desktop"


def test_m08_manager_is_loopback_only_on_dedicated_port() -> None:
    server = (DESKTOP / "manager-server.cmd").read_text(encoding="utf-8")
    ensure = (DESKTOP / "ensure-manager.ps1").read_text(encoding="utf-8")
    assert "--host 127.0.0.1 --port 8955" in server
    assert "http://127.0.0.1:8955/api/health" in ensure
    assert "Refusing to kill or replace" in ensure
    assert "state-reconcile" in ensure
    assert "active_deployment_transactions" in ensure
    assert "registry-reconcile.log" in ensure


def test_m08_headless_requires_current_repository_identity() -> None:
    ensure = (DESKTOP / "ensure-headless.ps1").read_text(encoding="utf-8")
    assert "ExpectedIndexPath" in ensure
    assert "index_path" in ensure
    assert "different Skills Manager source" in ensure


def test_m08_running_service_verification_checks_source_identity() -> None:
    verify = (ROOT / "scripts" / "qa" / "verify-local.ps1").read_text(encoding="utf-8")
    assert "MCP source identity mismatch" in verify
    assert "manager source identity mismatch" in verify
    assert "manager canonical truth is degraded" in verify


def test_m08_shortcut_opens_independent_manager_after_ensure() -> None:
    opener = (DESKTOP / "open-manager.ps1").read_text(encoding="utf-8")
    installer = (DESKTOP / "install-integration.ps1").read_text(encoding="utf-8")
    assert "ensure-manager.ps1" in opener
    assert 'Start-Process "http://127.0.0.1:8955/"' in opener
    assert "Skill Control Plane.lnk" in installer
    assert "local-prestart.cmd" in installer
    assert "Skill Control Plane integration BEGIN" in installer
    assert "local-launcher-overlay.cmd" not in installer
