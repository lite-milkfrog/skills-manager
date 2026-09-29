# Production Workflows

This directory contains version-controlled production Workflow specifications.

Current production families:

- `frontend-product-builder.v4.json`
- `creator-studio.v7.json`

Creator Studio v7 adds and hardens:
- NO-SILENT-SKIP workflow Skill coverage via `workflow-skill-auditor 1.1.0`
- `workflow_get` as the authoritative complete binding inventory
- `workflow_plan(..., include_optional=true)` as the full execution view
- machine coverage validation for preflight / stage / final gates
- onetake reference/rhythm/carry/anti-slideshow gates for VIDEO
- independent design, pre-export, final artifact, and final Skill-coverage audits

Older versions remain runtime history when they already exist in a local database.

Import with:

~~~powershell
.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older
~~~

The import is idempotent for existing Workflow IDs and preserves Run history. The production importer recovers the real Windows UserProfile so WAC sandbox HOME does not hide configured Skill roots.
