# Skills Manager Agent Contract

This repository is the standalone source of truth for Skills Manager. The stable WAC component id remains `skills-control-plane` for compatibility.

## Deployment dispatch

- If the user gives only this repository URL plus a request such as "deploy this project", treat it as a real deployment task, not a tutorial request.
- Before mutating the target machine, read `README.md` and `prompts/ONE-CLICK-AGENT-DEPLOY.md`, then execute discovery -> install/update -> verify -> handoff.
- Deploy the current default-branch HEAD unless the user explicitly requests a tag, commit, or release.
- Existing checkout: verify the remote, fetch the default branch, and only fast-forward a clean/non-divergent checkout.
- Never use `reset --hard`, `clean`, or discard unknown local work merely to reach latest.
- Dirty/diverged checkout: preserve it and use a fresh clone in a separate safe directory when possible.
- Record `SOURCE_REPOSITORY`, `SOURCE_BRANCH`, and `SOURCE_HEAD` in the final result.
- Deployment is incomplete until repository QA passes and the 8943 MCP passes initialize, tools/list, and a representative read-only Skills call.
- The 8955 Manager UI is optional for Agent execution.
- If WebGPT-as-Codex is present, install/update the WAC integration wrapper. WAC owns supervision/gateway routing; Skills Manager owns Skills/Workflow/Run source of truth.

## Repository invariants

- Do not reintroduce the historical `skill-control-plane` workspace as the long-term source of truth.
- Keep component id `skills-control-plane` and MCP endpoint `http://127.0.0.1:8943/mcp`.
- Preserve immutable Workflow/Run semantics and production Workflow artifacts under `workflows/`.
- Runtime databases, indexes, logs, PIDs, screenshots, caches, and machine-local environment files do not belong in Git.
