from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_native_deployment_contract_is_discoverable() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    prompt = (ROOT / "prompts" / "ONE-CLICK-AGENT-DEPLOY.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "deploy this project" in agents.lower()
    assert "prompts/ONE-CLICK-AGENT-DEPLOY.md" in agents
    assert "SOURCE_REPOSITORY" in prompt
    assert "SOURCE_BRANCH" in prompt
    assert "SOURCE_HEAD" in prompt
    assert "reset --hard" in prompt
    assert "scripts\\qa\\verify-local.ps1 -WithRunningServices" in prompt
    assert "8943" in prompt
    assert "https://github.com/lite-milkfrog/skills-manager" in readme
    assert "Please deploy this project." in readme
