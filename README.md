# Skills Manager

Local-first Skills registry, recursive capability resolver, immutable Workflow/Run engine, MCP server, and human manager UI.

This repository is the standalone source of truth for the project previously developed as Skill Control Plane. The stable MCP component ID remains `skills-control-plane` so existing WebGPT-as-Codex gateway bindings continue to work.

## Capabilities

- Canonical Skill discovery with explicit authority tiers and preserved variants
- `skills_search`, `skills_get`, `skills_resources`, and bounded recursive `skills_resolve`
- Router / Composite Skill preservation instead of flattening a top-level SKILL.md
- Versioned immutable Workflows, Runs, evidence, gates, retries, fallbacks, and audit history
- SQLite-backed local state with registry parity and integrity checks
- Loopback human manager UI
- WAC integration through the stable `skills-control-plane` component
- Version-controlled production Workflows:
  - Frontend Product Builder v4
  - Creator Studio v4

## Default endpoints

- MCP: http://127.0.0.1:8943/mcp
- MCP health: http://127.0.0.1:8943/healthz
- Manager UI/API: http://127.0.0.1:8955/

The Manager UI is optional. Agents read Skills and Workflows from the MCP/backend directly. Opening the UI is not part of the execution path.

## Fastest path: give the repository to an AI agent

Repository: **https://github.com/lite-milkfrog/skills-manager**

For a capable Windows coding/computer agent, the intended handoff is simply:

~~~text
https://github.com/lite-milkfrog/skills-manager
Please deploy this project.
~~~

The repository is self-dispatching for deployment. Root `AGENTS.md` directs the agent into `prompts/ONE-CLICK-AGENT-DEPLOY.md`, requires current default-branch HEAD verification, preserves dirty/diverged checkouts instead of resetting them, and continues through real 8943 MCP acceptance. The Manager UI on 8955 remains optional.

## Quick start on Windows

~~~powershell
git clone https://github.com/lite-milkfrog/skills-manager.git
cd skills-manager
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-headless.ps1
powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-manager.ps1
~~~

Open http://127.0.0.1:8955/ only when a human wants the management UI.

## Skill roots

Skills Manager works independently of WAC. It discovers standard user roots and can accept additional locations through:

- `SKILLS_MANAGER_EXTRA_ROOTS`
- `SKILLS_MANAGER_WORKSPACE_ROOT`
- `SKILLS_MANAGER_USER_HOME`
- `SKILLS_MANAGER_STATE_DIR`
- `SKILLS_MANAGER_STATE_SKILLS_ROOT`
- `SKILLS_MANAGER_LEGACY_CONFIG`

Legacy `SKILL_CONTROL_PLANE_*` environment variables remain accepted for compatibility.

If a WAC legacy Skills config exists under LocalAppData, it is read when available, but it is not required.

## Production Workflows

Workflow specifications are real repository artifacts under `workflows/`, not only rows in a local SQLite database.

Import them with:

~~~powershell
.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older
~~~

## WebGPT-as-Codex integration

Install the local WAC component/ensure wrapper:

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\desktop\install-integration.ps1
~~~

Compatibility contract:

- component id: `skills-control-plane`
- display name: Skills Manager
- MCP endpoint: 8943
- Manager endpoint: 8955
- WAC gateway exposure: gateway
- dependency: mcpjungle

The standalone repository owns Skills Manager source and Workflow specs. WAC owns the integration declaration and gateway/runtime relationship.

## Verify

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\qa\verify-local.ps1
~~~

Add `-WithRunningServices` to also check the live 8943 and 8955 endpoints.

## Repository hygiene

Runtime databases, indexes, screenshots, logs, PIDs, local caches, local Serena state, and environment files are intentionally excluded from Git. Runtime state belongs to the machine, not the repository.
