# Skills Manager — One-Click Agent Deployment

Give this repository URL to a Windows-capable coding/computer agent and ask it to deploy the project. The agent should execute the deployment, not merely explain it.

```text
# SKILLS MANAGER — AGENT-NATIVE ONE-CLICK DEPLOY

REPOSITORY = <this repository URL or local checkout>
TARGET = current Windows user machine
PRODUCT = Skills Manager
COMPONENT_ID = skills-control-plane
MCP = http://127.0.0.1:8943/mcp
MANAGER = http://127.0.0.1:8955/

## 0. Source Freshness Gate

- Treat the user-supplied repository URL as source of truth.
- Resolve its current default branch and latest remote HEAD. A generic "deploy this project" means deploy that HEAD unless the user explicitly requests a tag/commit/release.
- Fresh machine: clone the current default branch.
- Existing checkout: verify remote, fetch the default branch, compare local HEAD with origin/<default-branch>, and only fast-forward when clean and non-divergent.
- Never reset --hard, clean, or overwrite unknown local work merely to reach latest.
- Dirty/diverged checkout: preserve it and use a fresh clone in a separate safe directory when possible.
- Immediately before install, fetch again and record SOURCE_REPOSITORY / SOURCE_BRANCH / SOURCE_HEAD.
- Confirm deployed HEAD equals the fetched remote default-branch HEAD.

## 1. Required reading

1. AGENTS.md
2. README.md
3. prompts/ONE-CLICK-AGENT-DEPLOY.md

## 2. Environment and install
- Confirm Windows, Git, Python >= 3.11, and Node for Manager JavaScript verification.
- From the verified checkout:
  `py -3 -m venv .venv`
  `.\.venv\Scripts\python -m pip install -e ".[dev]"`
- Import production Workflows:
  `.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older`
- Start/ensure the headless MCP:
  `powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-headless.ps1`
- Start/ensure the Manager only when useful:
  `powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-manager.ps1`
- If WebGPT-as-Codex is installed or is the target integration, install the integration wrapper:
  `powershell -ExecutionPolicy Bypass -File scripts\desktop\install-integration.ps1`

## 3. Verification

Run:
`powershell -ExecutionPolicy Bypass -File scripts\qa\verify-local.ps1 -WithRunningServices`

Acceptance requires:
- repository regression tests PASS;
- Ruff PASS for maintained source/tests;
- Manager app.js and i18n.js syntax PASS;
- no machine-specific path leakage from portable source/scripts;
- 8943 /healthz healthy;
- MCP initialize succeeds;
- tools/list succeeds and exposes the expected Skills/Workflow/Run tool surface;
- a representative read-only Skills call succeeds;
- 8955 /api/health succeeds if the Manager is started;
- production Workflow specs are imported from this repository.

If WAC is present, also verify:
- WAC external-ensure binding points to this standalone skills-manager checkout;
- component id remains skills-control-plane;
- WAC gateway exposure remains gateway;
- no duplicate historical skill-control-plane runtime is introduced.

## 4. Final result

Report:
- SOURCE_REPOSITORY
- SOURCE_BRANCH
- SOURCE_HEAD
- install/update action taken
- test/QA result
- 8943 MCP acceptance result
- optional 8955 Manager result
- WAC integration result when applicable
- any human-only blocker

Do not claim "latest" without remote HEAD evidence.
```
