# Production Workflows

This directory contains version-controlled production Workflow specifications.

Current production families:

- `frontend-product-builder.v6.json`
- `creator-studio.v9.json`

## Unified autonomous audit

Both production workflows use one required audit Skill:

- `autonomous-stage-auditor 2.0`

It is a lossless capability union of the former:

- `workflow-skill-auditor`
- `autonomous-stage-auditor 1.x`
- `loop-orchestrator`
- `proof-loop`
- `gauntlet-loop`
- `design-loop`

The source trees are preserved with SHA256 manifests under:

`D:\AgentData\40_Archive\audit-skill-lossless-merge-20260929`

Runtime behavior is now mode-routed inside one Skill:

- FAST
- PROOF
- ADVERSARIAL
- DESIGN
- CREATIVE
- COVERAGE

This removes repeated Skill loading while preserving the strict invariants:

```
freeze target
  -> produce actual artifact
  -> capture evidence
  -> independent/cold audit
  -> FAIL/UNKNOWN ? repair/strategy reset : PASS
  -> only PASS may advance
```

Creator Studio v9 keeps stage-by-stage audit across all 14 stages with one audit binding per stage.

Frontend Product Builder v6 keeps stage-by-stage audit across all 7 stages; visual stages select DESIGN internally, engineering/browser stages PROOF, and high-impact polish DESIGN + ADVERSARIAL.

`workflow_get` remains the authoritative complete binding inventory. The merged auditor owns NO-SILENT-SKIP coverage and stage-quality gating together.

Older Workflow versions remain runtime history.

Import with:

~~~powershell
.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older
~~~
