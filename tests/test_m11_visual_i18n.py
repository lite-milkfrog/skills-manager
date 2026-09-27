from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "manager"


def test_m11_visual_system_and_new_theme_modes_exist() -> None:
    design = (ROOT / "design" / "M11-VISUAL-SYSTEM.md").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "M10 screenshot" in design
    assert "Default = light." in design
    assert "old dark admin console" in design
    assert "html { color-scheme: light;" in styles
    assert 'content="light dark"' in index
    assert "scp-theme" in index
    assert 'data-theme="dark"' in styles
    assert 'id="themePreference"' in index


def test_m11_beginner_copy_is_english_source_with_centralized_zh_cn() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "Skills are reusable AI capabilities." in app
    assert "Browse by use case" in app
    assert "What does this Skill do?" in app
    assert "Maintenance, troubleshooting and system-level tools live here." in app

    for stale_literal in (
        "这里收集的是可复用的 AI 能力",
        "按用途找技能",
        "不知道技能名也没关系",
        "这个 Skill 是做什么的",
        "这里是维护和排错信息",
        "这里放的是维护、排错和系统级能力",
    ):
        assert stale_literal not in app

    assert "'Browse by use case': '按用途找技能'" in i18n
    assert "'What does this Skill do?': '这个 Skill 是做什么的？'" in i18n
    assert "'skills.browsingUseCase'" in i18n
    assert "'home.availableSkills'" in i18n
    assert "scp.locale" in i18n


def test_m11_keeps_one_frontend_and_progressive_disclosure() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'data-route="overview"' in index
    assert 'data-route="skills"' in index
    assert 'data-route="workflows"' in index
    assert 'data-route="runs"' in index
    assert 'data-route="advanced"' in index
    assert "const primaryTabs = ['about', 'organization', 'technical']" in app
    assert "legacyTechnicalTabs" in app
    assert "#/system/health" in app
    assert "#/deployments" in app

    for duplicate in ("index.zh-CN.html", "index.en.html", "app.zh-CN.js", "app.en.js"):
        assert not (WEB / duplicate).exists()


def test_m11_uses_project_owned_brand_and_svg_icon_system() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    icons = (WEB / "assets" / "icons.svg").read_text(encoding="utf-8")

    assert "/assets/skill-control-plane-mark.svg" in index
    assert "/assets/icons.svg#home" in index
    assert "/assets/icons.svg#" in app
    assert '<symbol id="home"' in icons
    assert '<symbol id="search"' in icons
    assert '<symbol id="agent"' in icons


def test_m11_dynamic_runtime_status_is_not_reset_by_static_i18n() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'id="navStatusText">Checking local runtime…</span>' in index
    assert 'id="healthPill" aria-live="polite">Runtime…</div>' in index
    assert 'id="navStatusText" data-i18n=' not in index
    assert 'id="healthPill" aria-live="polite" data-i18n=' not in index


def test_m11_treats_skills_as_recursive_capability_entry_points() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "const CAPABILITY_KINDS" in app
    assert "Single Skill" in app
    assert "Composite Skill" in app
    assert "Router Skill" in app
    assert "Agent & tool Skill" in app
    assert "loadSkillCapabilityBundle" in app
    assert "/body')" in app
    assert "/resources')" in app
    assert "Detected inner Skills" in app
    assert "Capability bundle" in app
    assert "Route / orchestration chain" in app

    prompt_rules = (
        "Treat every selected Skill as a capability entry point"
    )
    assert prompt_rules in i18n
    assert "open and read the selected SKILL.md in full" in i18n
    assert "routing.md/routes.md, workflows/, references/, scripts/, assets/, EVOLUTION.md" in i18n
    assert "internal route Skills, canonical child Skills, and MCP/tool protocols" in i18n
    assert (
        "router Skill remains unresolved until its route reaches the actual executable capability"
        in i18n
    )
    assert "Keep that internal workflow intact" in i18n
    assert "Discover and use the MCP/tools required by the resolved capability route" in i18n


def test_m11_explains_skills_workflows_and_tools_as_three_layers() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "How the Agent works" in app
    assert "Skills are entry points, not flat commands." in app
    assert "Composite Skills can stay intact inside one step." in app
    assert "Tools & MCP" in app
    assert "section === 'tools'" in app
    assert "renderAgentTools()" in app
    assert "Keep nested workflows and routes intact." in app


def test_m11_skill_model_is_recursive_not_flat() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
    design = (ROOT / "design" / "M11-VISUAL-SYSTEM.md").read_text(encoding="utf-8")

    assert "CAPABILITY_KINDS" in app
    assert "Single Skill" in app
    assert "Composite Skill" in app
    assert "Router Skill" in app
    assert "Agent & tool Skill" in app
    assert "analyzeSkillContent" in app
    assert "Read this Skill fully first." in app
    assert "workflow.prompt.rules" in i18n
    assert "SKILL.md" in i18n
    assert "references/" in i18n
    assert "composite/router Skill" in i18n
    assert "A Skill is an execution entry point, not a flat prompt token." in design


def test_m11_recursive_capability_resolution_is_bounded_and_recoverable() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "visited.has(normalized)" in app
    assert "if (depth > 0)" in app
    assert "analysis.childSkills.slice(0, 8)" in app
    assert "selected.length < 64" in app
    assert "rootAnalysis.kind === CAPABILITY_KINDS.router" in app
    assert "references\\/routes\\.md" in app
    assert "unresolved: true" in app
    assert "Only use these Skills" not in app
    assert "Only use these Skills" not in i18n
    assert app.index("if (hasToolProtocol && hasAgentProtocol)") < app.index(
        "route selection|routing skill"
    )
    assert "rootAnalysis.kind === CAPABILITY_KINDS.agent" in app
    assert "? CAPABILITY_KINDS.agent" in app


def test_m11_beginner_skill_library_can_browse_by_location() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "LOCATION_GROUPS" in app
    assert "browse=location" in app
    assert "Workspace Skills" in app
    assert "WorkBuddy Skills" in app
    assert "Trae Skills" in app
    assert "ChatBox built-in Skills" in app
    assert "Archived Skills" in app
    assert "'Browse by location': '按位置分类'" in i18n


def test_m11_workflow_builder_generates_beginner_agent_prompt() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")

    assert "workflowAgentPrompt" in app
    assert "workflowPromptPanel" in app
    assert "Copy Agent prompt" in app
    assert "Read each Skill fully" in app
    assert "Keep nested workflows intact" in app
    assert '<details class="workflow-prompt-details">' in app
    assert "This Skill\\'s advanced options" in app
    assert "updateSelectedSkillPreview" in app
    assert "'Copy Agent prompt': '复制 Agent 提示词'" in i18n


def test_m11_explains_tools_and_mcp_without_replacing_advanced_routes() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "renderAgentTools" in app
    assert "section === 'tools'" in app
    assert "#/tools" in app
    assert "Coding Tools" in app
    assert "Playwright" in app
    assert "Remote Desktop Commander" in app
    assert "Serena" in app
    assert "Windows-MCP" in app
    assert "renderAdvanced" in app
    assert "#/advanced" in app
