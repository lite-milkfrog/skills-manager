# SCP-M05 Visual Direction

PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922

## 1. Character

The product should read as a serious local developer/admin instrument: dense, calm and inspectable. It should not resemble a generic blue-purple AI analytics dashboard and should not use chat as the primary interaction metaphor.

Reference patterns were reviewed read-only from:

- VS Code Extension Marketplace documentation — dense browse/search/filter, stable extension identity and list-to-detail behavior.
- GitHub Actions monitoring documentation — run-centric history, status, step/log evidence and execution visualization.
- Temporal Web UI documentation — Workflow Execution tables, status/ID/time filtering, deep execution history and saved/deep-linkable views.

These are interaction references only; no product is cloned.

## 2. Layout

Desktop-first:

- left navigation 220–248 px expanded, 52–64 px collapsed;
- top global search/command strip;
- content max width is generally unconstrained for tables;
- detail pages use a 12-column grid;
- optional right inspector 360–440 px for quick comparison;
- sticky table headers and sticky detail action bar where helpful.

Density target:

- 32–38 px compact table rows;
- 12–14 px primary UI text;
- 16–20 px section headings;
- 24–30 px page titles;
- 4/8 px spacing rhythm.

## 3. Typography

Use native/local-friendly stacks to avoid a font dependency:

- UI: Segoe UI / Inter-compatible system sans.
- IDs, paths, hashes, JSON and Skill body code: Cascadia Mono / JetBrains Mono-compatible system mono.

Canonical IDs use mono styling and subdued contrast. Human names remain the primary scan target.

## 4. Color semantics

Base surfaces: graphite/slate/neutral gray with high-contrast text. Light and dark themes can share semantic tokens.

Interactive accent: restrained teal/cyan-green or neutral high-contrast accent, not a saturated blue-purple gradient.

Semantic color is reserved:

- healthy/completed/valid: green;
- running/selected attention: cool accent;
- blocked/degraded/dry-run caution: amber;
- invalid/failed: red;
- physical-risk/future apply: stronger red border/background tint;
- historical/non-selectable/read-only: neutral slate.

Color is always paired with text/icon state.

## 5. Component direction

### Tables

- sticky header;
- resizable/truncating columns where practical;
- explicit sort state;
- compact chips;
- row hover and keyboard selection;
- no zebra-striping strong enough to reduce density.

### Inspectors

Quick inspector for selected row, full-page route for deep work. Inspector contains metadata only until Body is explicitly opened.

### Drawers/dialogs

Use drawers for filters and metadata organization. Use dialogs for destructive metadata deletion and future physical confirmation.

### Timelines

Run evidence/audit use a vertical chronological rail. Stage order uses a compact ordered rail. Evidence kinds and audit transitions use different glyph/label treatment.

### Workflow editor

Structured stages are cards/sections with ordinal handles and validation state. A compact visual strip to the side shows deterministic order and fallback edges. No free-form canvas.

### Code/body views

Monospace, line-wrap toggle, copy selection/path, sticky source header, digest/path context. Large bodies are independent scroll regions only when accessibility is preserved.

## 6. Risk distinction

Metadata actions use neutral controls and the phrase “Organize metadata”.

Physical intent uses a separate Deployments context, amber/red risk border and “Plan relocation/deployment” language. Future apply is disabled and cannot visually resemble a normal Save button.

## 7. Motion

Restrained 120–180 ms transitions for drawers, hover/focus and stage expansion. No animated charts or pulsing status decoration. Honor reduced-motion.

## 8. Responsive behavior

- >= 1200 px: full nav, table and optional inspector.
- 900–1199 px: collapsed nav optional; inspector becomes overlay/drawer.
- 700–899 px: filters become drawer, detail columns stack, tables keep horizontal scroll rather than converting every row into giant cards.
- <700 px: supported for inspection and simple actions, not optimized as a mobile-first workflow editor; stage editor becomes stacked.

No information is removed solely because the window is narrow; secondary metadata can collapse into expandable rows.

## 9. Focus and contrast

- visible 2 px-equivalent focus treatment;
- minimum WCAG AA text contrast;
- no status via color alone;
- hover is never the only way to reveal essential action;
- physical-risk confirmations use text heading + icon + semantic color;
- disabled controls include a textual reason when the action is intentionally unavailable.
