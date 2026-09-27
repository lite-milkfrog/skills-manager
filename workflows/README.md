# Production Workflows

This directory contains version-controlled production Workflow specifications.

Current production families:

- `frontend-product-builder.v4.json`
- `creator-studio.v4.json`

Older versions remain runtime history when they already exist in a local database, but they are not duplicated here as active production definitions.

Import with:

~~~powershell
.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older
~~~

The import is idempotent for existing Workflow IDs and preserves Run history.
