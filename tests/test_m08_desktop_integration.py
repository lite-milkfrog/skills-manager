from pathlib import Path

ROOT = Path(__file__).parents[1]
DESKTOP = ROOT / "scripts" / "desktop"


def test_m08_manager_is_loopback_only_on_dedicated_port() -> None:
    server = (DESKTOP / "manager-server.cmd").read_text(encoding="utf-8")
    ensure = (DESKTOP / "ensure-manager.ps1").read_text(encoding="utf-8")
    assert "--host 127.0.0.1 --port 8955" in server
    assert "SKILLS_MANAGER_USER_HOME" in server
    assert "GetFolderPath" in server
    assert "SKILLS_MANAGER_USER_HOME" in ensure
    assert "SpecialFolder]::UserProfile" in ensure
    assert "http://127.0.0.1:8955/api/health" in ensure
    assert "Refusing to kill or replace" in ensure
    assert "state-reconcile" in ensure
    assert "active_deployment_transactions" in ensure
    assert "registry-reconcile.log" in ensure


def test_m08_headless_requires_current_repository_identity() -> None:
    server = (DESKTOP / "headless-server.cmd").read_text(encoding="utf-8")
    ensure = (DESKTOP / "ensure-headless.ps1").read_text(encoding="utf-8")
    assert "SKILLS_MANAGER_USER_HOME" in server
    assert "GetFolderPath" in server
    assert "SKILLS_MANAGER_USER_HOME" in ensure
    assert "SpecialFolder]::UserProfile" in ensure
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


def test_m08_production_import_recovers_real_windows_profile() -> None:
    importer = (ROOT / "scripts" / "workflows" / "import-production.py").read_text(
        encoding="utf-8"
    )
    assert "_ensure_production_user_home" in importer
    assert "SKILLS_MANAGER_USER_HOME" in importer
    assert "SHGetFolderPathW" in importer
    assert "stable_id" in importer
    assert "_workflow_exists" in importer
    assert "SELECT 1 FROM workflows WHERE workflow_id=?" in importer
