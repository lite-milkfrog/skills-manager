from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "manager"


def test_m10_primary_navigation_is_beginner_first() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'data-i18n="Home"' in index
    assert 'data-i18n="Skill Library"' in index
    assert 'data-i18n="Automations"' in index
    assert 'data-i18n="Activity"' in index
    assert 'data-i18n="Advanced Tools"' in index
    assert 'data-route="deployments"' not in index
    assert 'data-route="system"' not in index


def test_m10_home_and_skill_library_hide_technical_truth_by_default() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "What do you want AI to help with?" in app
    assert "'What do you want AI to help with?': '你想让 AI 帮你做什么？'" in i18n
    assert "useCaseGrid()" in app
    assert "skill-card-grid" in app
    assert "Advanced mode" in app
    assert "'Advanced mode': '高级模式'" in i18n
    assert "renderAdvanced()" in app


def test_m10_skill_detail_uses_progressive_disclosure() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "const primaryTabs = ['about', 'organization', 'technical']" in app
    assert "What it does" in app
    assert "Technical details" in app
    assert "This is maintenance and troubleshooting information." in app
    assert "Raw SKILL.md" in app


def test_m10_versioned_production_workflows_are_repository_artifacts() -> None:
    import json

    frontend = json.loads(
        (ROOT / "workflows" / "frontend-product-builder.v4.json").read_text(
            encoding="utf-8"
        )
    )
    creator = json.loads(
        (ROOT / "workflows" / "creator-studio.v4.json").read_text(encoding="utf-8")
    )

    assert frontend["version"] == 4
    assert creator["version"] == 4
    frontend_skills = {
        binding["skill_id"]
        for stage in frontend["stages"]
        for binding in stage.get("bindings", [])
    }
    assert {
        "ui-design",
        "frontend-design",
        "web-development",
        "webapp-testing",
        "impeccable",
    }.issubset(frontend_skills)

    assert "VIDEO" in creator["description"]
    assert "GRAPHIC/CAROUSEL" in creator["description"]
    assert "HYBRID" in creator["description"]
    creator_skills = {
        binding["skill_id"]
        for stage in creator["stages"]
        for binding in stage.get("bindings", [])
    }
    assert "human-writing" in creator_skills
    assert "knowledge-notes" in creator_skills
