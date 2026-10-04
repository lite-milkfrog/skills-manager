# Skills Manager

**English** | [简体中文](README.zh-CN.md)

Local-first Skills registry, recursive capability resolver, versioned Workflow/Run engine, MCP server, and human manager UI.

This repository is the standalone source of truth for the project previously developed as Skill Control Plane. It works on its own, but it is also the official Skills / Workflow companion to WebGPT-as-Codex. The stable MCP component ID remains `skills-control-plane` so existing WAC gateway bindings continue to work.

## Why this exists when your computer already has Skills

If you only have a handful of Skills, you may not need this project. An agent can search a folder, open the matching `SKILL.md`, and keep going.

The problem changes when the machine has hundreds or thousands of Skills spread across `.agents`, project folders, Obsidian vaults, copied plugins, historical variants, and tool-specific roots. At that point the question is no longer just **“can I find a Skill with this name?”** It becomes **“which variant should win, what does it depend on, which Skill owns this Stage, and what has to pass before the workflow moves on?”**

A filesystem search is good at finding files. Skills Manager is meant to make the collection **structured enough for an Agent to reason over**:

- discover Skills across multiple roots without flattening away authority tiers or conflicting variants;
- expose structured `skills_search`, `skills_get`, `skills_resources`, and recursive `skills_resolve` calls instead of forcing every Agent to grep a large tree manually;
- let Workflows bind **Stage -> Skill -> gate -> next Stage**, so “when should I use this Skill?” becomes data rather than chat-memory folklore;
- persist Workflow versions, Runs, evidence, retries, fallbacks, blockers and audit history in a machine-readable form;
- keep the human UI optional. Agents use the MCP/backend directly; the UI exists for inspection and management, not as a required execution path.

So Skills Manager does not replace your local Skills. It gives them an index, an authority model, and an execution structure.

> **Skills answer “what can I do?” Skills Manager answers “which capability owns this Stage, how should I resolve it, and what must be true before I advance?”**

## Standalone project, WAC companion

Skills Manager deliberately stays in its own repository. It can be deployed without WAC, and its source, database model and production Workflow specs belong here.

When WebGPT-as-Codex is present, WAC registers this project as the stable `skills-control-plane` component and exposes it through the same unified Gateway. WAC owns gateway/runtime integration; Skills Manager owns Skill discovery, resolution, Workflow definitions, Runs, gates and evidence.

That split matters for remote use too. Skills Manager itself may stay loopback-only on port 8943. WAC can put it behind the same OAuth-protected HTTPS MCP entry point as Coding Tools, Serena, Playwright and other local MCPs. Any desktop or mobile client that actually supports MCP and can complete the configured network/authentication flow can then reach the structured Skills/Workflow layer without exposing the raw backend directly.

## Capabilities

- Canonical Skill discovery with explicit authority tiers and preserved variants
- `skills_search`, `skills_get`, `skills_resources`, and bounded recursive `skills_resolve`
- Router / Composite Skill preservation instead of flattening a top-level SKILL.md
- Versioned immutable Workflows, Runs, evidence, gates, retries, fallbacks, and audit history
- SQLite-backed local state with registry parity and integrity checks
- Loopback human manager UI
- WAC integration through the stable `skills-control-plane` component
- Version-controlled production Workflows:
  - Frontend Product Builder v6
  - Creator Studio v9
  - WebGPT-as-Codex Loop Engineering v1
  - WebGPT-as-Codex Parallel Agent Orchestration v1

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

Workflow specifications are real repository artifacts under `workflows/`, not only rows in a local SQLite database. This is where the structured “what Skill owns what Stage?” relationship becomes version-controlled instead of living only in one Agent session.

The current repository-backed production families are Frontend Product Builder v6, Creator Studio v9, WAC Loop Engineering v1, and WAC Parallel Agent Orchestration v1. Older files remain as history where useful.

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

The standalone repository owns Skills Manager source, Skill/Workflow semantics and Workflow specs. WAC owns the integration declaration, remote exposure and gateway/runtime relationship. WAC deployment also synchronizes its canonical Skill and imports the repository-backed production Workflows, so an Agent can resolve both individual Skills and stage-level execution structure through one MCP surface.

## Verify

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\qa\verify-local.ps1
~~~

Add `-WithRunningServices` to also check the live 8943 and 8955 endpoints.

## Repository hygiene

Runtime databases, indexes, screenshots, logs, PIDs, local caches, local Serena state, and environment files are intentionally excluded from Git. Runtime state belongs to the machine, not the repository.