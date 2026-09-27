# SCP-M05 Web Product Specification

STABLE_CORE_VERSION = LE-STABLE-2026-09-17.2
PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922
STAGE = SCP-M05-WEB-PRODUCT-DESIGN

## 1. Product statement

Skill Control Plane Manager is a local developer/admin surface over the already-closed headless control plane. It is not a chat wrapper, file manager, second scanner, second workflow engine, or alternate state database.

The Manager exposes six existing truth domains without changing their ownership:

1. **Discovery** — canonical Skill identity, selected source, variants, source authority, validation/evaluation and lazy Skill body.
2. **Organization** — categories, tags and contextual associations stored as metadata only.
3. **Workflow** — immutable name/version definitions, ordered stages, canonical Skill bindings, gates, bounded retry/loop and fallbacks.
4. **Run** — durable execution state, current stage, resolved bindings, evidence, audit, blocked/resume and terminal result.
5. **Deployment** — M03 safety model, dry-run plans, managed-location and transaction truth; no public physical apply in the M04 contract.
6. **System health** — Discovery counts, public route/service identity, source authority, SQLite parity/integrity and deployment activity.

Skill bodies remain on filesystem. Discovery identity remains M01-authoritative. SQLite remains canonical for management/workflow/run/deployment metadata after reconcile parity.

## 2. Product principles

- **Truth before convenience.** Selected, selectable, authority tier and source class are distinct concepts and are never collapsed into one vague “active/latest” badge.
- **Metadata is not movement.** Categories/tags/grouping never imply a filesystem move. Physical relocation appears only in Deployment/Locations and always uses M03 semantics.
- **Metadata-first at scale.** The inventory currently contains 2321 selected Skills and 6630 variants. Lists never eagerly fetch full SKILL.md bodies.
- **Deterministic workflows stay visually deterministic.** Ordered stages are primary. A visual path summary may clarify flow, but a free-form node graph is not the editing source of truth.
- **Server authority wins.** UI affordances may predict whether an action is legal, but transition/deployment validation remains authoritative in the existing services.
- **Physical risk is visually and behaviorally isolated.** Dry-run is first-class. Physical apply remains unavailable until an explicit typed backend contract exists.
- **Deep-linkable administration.** Skills, workflows and runs have stable detail routes. IDs are available for precision without dominating normal reading.

## 3. Real grounding used by this design

Current accepted M04 truth:

- 2321 selected Skills / 6630 variants / 373 non-selectable variants / 417 invalid discovery inputs / 7035 explicit files.
- SQLite schema v3, parity PASS, integrity_check ok, zero FK violations.
- 4 real workflows, 4 real runs and 111 audit rows currently exist.
- Categories, tags, workspaces, agents and management-plane deployment metadata are currently empty, so first-use states are required.
- Current public route is 9330 -> skills-control-plane -> 8943; 8942 remains the tested rollback target.
- Public Skill Control Plane surface is exactly six Discovery tools plus ten narrow Workflow/Run/deployment-dry-run tools.

Representative identity evidence:

- `webgpt-as-codex` has 19 variants. Its selected source is project_portable/authority 1000, while selectable alternatives exist at authority 900/850/825/650 and historical_archive copies are non-selectable at authority 0.
- `computer-agent` demonstrates that the selected available source can still be historical_explicit/authority 100. Therefore “selected” must never be rendered as a synonym for “newest”, “recommended” or “safe”.

Representative run evidence:

- Real browser run `run_e9359f870454551afd5f` reconstructs task -> workflow -> stage -> required `webgpt-as-codex` binding -> Playwright evidence -> completion.
- Real local run `run_b959d0aea80d00e6bc75` reconstructs a required `computer-agent` binding and Coding Tools evidence.
- `run_e69cf8e02edd75416505` proves blocked -> evidence -> resume -> complete and illegal duplicate resume rejection.
- `run_80085d76b75cbf75917d` proves a Workflow-linked M03 deployment dry-run with zero physical mutation.

## 4. Mutation/risk classes

| Class | Meaning | Examples | Default confirmation |
|---|---|---|---|
| R0 READ_ONLY | Reads or deterministic previews; no durable user mutation | search, get, validate, evaluate, workflow plan, run inspect, health, copy path | none |
| R1 METADATA_MUTATION | SQLite metadata only; Skill bodies/locations unchanged | categories, tags, bindings, workflow new version, workspace/agent metadata | inline review; confirm destructive delete |
| R2 RUN_STATE_MUTATION | Durable execution-state transition/evidence | create/start/block/evidence/resume/succeed | contextual action confirmation only where consequences are non-obvious; server revalidates |
| R3 PHYSICAL_PLAN_ONLY | High-risk intent preview, but no physical write | deployment_plan | no physical confirmation; show explicit “Dry run only” banner |
| R4 PHYSICAL_APPLY | Filesystem-changing transaction under M03 | future deploy/update/relocate/undeploy/recover/rollback | mandatory plan freshness + explicit confirmation; disabled until typed backend exists |
| L1 LOCAL_UI_SIDE_EFFECT | Non-data local OS action bound to canonical record | Open containing folder in Explorer | none; typed allowlisted action only |

R4 is **not enabled by M05** and must not be simulated by raw file operations in M06.

## 5. Primary user journeys

### J1 — Find a Skill quickly

1. Open Skills or invoke global search.
2. Search name/description/path keywords without loading bodies.
3. Narrow by source class, authority band, selected source state, selectable state, validation state, category/tag and variant count.
4. Open a stable Skill detail route.
5. Only then load full body or variant details as requested.

Success: thousands of entries remain navigable without serial full-body reads.

### J2 — Understand canonical identity and authority

The detail header shows human name first and canonical `skill_id` as secondary mono text. “Selected source” is a distinct summary card containing source class, authority tier, selectable state, digest prefix and path. Variants are grouped into:

1. Selected canonical source.
2. Alternate selectable variants, ordered by actual authority semantics.
3. Non-selectable/historical variants.
4. Invalid discovery inputs are not represented as valid variants; they live in Discovery Issues/System health.

No label such as “latest” is inferred from selection.

### J3 — Organize without moving files

From a Skill’s Organization tab or multi-select action:

- attach/remove category;
- attach/remove tags;
- inspect workspace/agent associations when available.

A persistent helper label states **“Metadata only — file location will not change.”** The path field stays unchanged. “Move” is never used for this operation.

### J4 — Inspect Skill body lazily

Body is an explicit tab/action. Opening it calls the selected Skill detail capability and renders Markdown/code with line wrapping controls. The inventory table and search results never request bodies. Variant body inspection is only enabled where an explicit path-capable validation/read contract exists; selected full body remains the guaranteed M04 path.

### J5 — Inspect/edit Workflow definitions

Existing versions are immutable in product behavior because the closed service creates a stable name+version identity and rejects duplicates. “Edit workflow” means **Create new version**:

1. Load current definition.
2. Prefill a structured copy with an incremented version.
3. Edit ordered stages and canonical Skill bindings.
4. Dry-run normalization/validation.
5. Review deterministic plan.
6. Create the new version.

No in-place schema mutation is implied.

### J6 — Understand a Run end-to-end

Run detail reads as:

Task/context -> workflow/version -> ordered run stages -> resolved canonical bindings -> evidence/audit -> terminal result.

The header shows status and current stage. Stage panels expose retries/loops/gates. Evidence and audit are chronological but visually distinguish evidence from state transitions.

### J7 — Resolve a blocked Run

Blocked state gets a dedicated banner with the persisted reason, current stage and current durable evidence. Resume is disabled client-side when status is not blocked or there is no evidence, but that is only convenience: `run_resume` remains authoritative. A rejected/duplicate resume refreshes the run and surfaces the typed transition error rather than retrying blindly.

The UI does not fabricate an “evidence checklist” from free-form reason text unless the workflow/gate explicitly provides structured requirements.

### J8 — Preview safe deployment/relocation intent

Deployment builder begins with Skill identity and operation, then source/target. “Preview dry run” calls the M03 plan adapter. Result shows:

- plan_id / transaction_id;
- operation;
- source/target;
- ownership class;
- expected digests;
- preconditions;
- target-absence/collision expectations;
- protected-target, drift, historical/non-selectable and reparse rejection errors.

The apply region is visibly disabled with “Physical apply is not exposed by the accepted M04 contract.”

### J9 — Open a Skill location in Explorer

Skill/variant details may show **Open containing folder**. M06 must implement this as a typed local action bound to a canonical record/variant, with the backend resolving and validating the real local directory. It must not accept or execute an arbitrary shell command. This is DESIGN_READY_BACKEND_GAP.

### J10 — Never confuse organization with relocation

- Category/tag action copy: “Organize metadata”.
- Filesystem action copy: “Plan relocation”.
- Metadata actions use ordinary neutral styling.
- Relocation entry lives only in Deployments/Locations, uses high-risk styling and always begins with dry-run.
- There is no generic “Move Skill” menu item.

## 6. Skills experience

### Primary list

Use a **compact virtualized table**, not cards, as the primary representation. Cards waste vertical space and obscure comparison across thousands of records. Optional compact card view is not required for M06.

Recommended columns:

- Skill — name + compact description;
- Selected source — source_class;
- Authority — numeric tier plus semantic badge;
- Variants — total with selectable/non-selectable split;
- Organization — category/tag chips, truncated;
- Health — valid/degraded/invalid/unknown;
- Location — ellipsized path with copy action.

Canonical skill_id appears on hover/detail and as a secondary line only where name differs or disambiguation matters.

### Filters

Facets:

- query;
- source_class;
- authority tier/band;
- selected source;
- selectable/non-selectable presence;
- validation/issue state;
- variant-count range;
- category/tag;
- category_router where useful.

Filters must be URL-serializable for deep links.

### Skill detail

Tabs:

1. Overview
2. Variants
3. Body
4. Validation
5. Organization
6. Relations

Overview shows selected identity and source hierarchy. Variants explicitly group selected / alternate selectable / non-selectable historical. Body is lazy. Validation calls the existing validator. Evaluation presents a task-query field and ranking explanation/result. Organization is metadata-only. Relations shows workflow/workspace/agent references when backend read contracts exist.

Path controls: copy path is client-side; Open containing folder is typed backend gap.

## 7. Workflow experience

Primary editor is **split structured + visual summary**:

- main pane: ordered stage editor;
- secondary pane: deterministic plan strip showing stage sequence, gates, retry/loop and fallback edges.

The visual strip is generated from the same workflow structure and is never separately editable. This avoids a second workflow schema and makes ordered execution obvious.

Stage editor fields map one-to-one to the closed service:

- key / ordinal;
- condition;
- success_gate;
- failure_gate;
- retry_limit;
- loop_limit;
- loop_stop_condition;
- fallback_stage;
- bindings[]:
  - key;
  - canonical skill_id picker;
  - required / optional / conditional;
  - binding condition;
  - fallback_skill_id.

Skill picker searches canonical IDs through Discovery metadata. It does not copy Skill bodies into workflow state.

Validation errors preserve typed/backend error codes next to the exact stage/binding and in a summary panel. Deterministic preview uses workflow dry-run for an unsaved version and workflow_plan for a stored version.

Version behavior:

- stored versions are read-only;
- Create new version copies the existing definition into a new version number;
- duplicate name/version is an error;
- no “Save over v1” behavior is designed.

## 8. Run/evidence experience

Run list is a dense table with URL-serializable filters for status, workflow/version, current stage, Skill binding and time. Backend pagination/listing is an explicit M06 gap.

Run inspector:

- header: run_id, status, workflow/version, task/context, current stage, timestamps where available;
- ordered stage rail: pending/running/blocked/succeeded/failed;
- selected stage inspector: resolved bindings, retry/loop counters, gate result, blocked reason;
- evidence timeline: kind, payload summary, timestamp, stable evidence_id;
- audit timeline: action, entity, timestamp, payload summary;
- terminal card: completed/failed result.

Status semantics must distinguish planned, active/running, blocked, completed and failed. State-changing buttons are derived from current snapshot but server rejection is authoritative. On TransitionError, display the error and refresh rather than auto-retry.

## 9. Deployment/physical-safety experience

Deployment has two subviews:

- **Plan Builder** — available from the existing dry-run adapter.
- **Locations & Transactions** — read-only product design; backend listing adapters are gaps.

Plan builder must render M03 policy outcomes directly. Specific errors such as protected target, destination collision, selected-source drift, managed-path drift, historical/non-selectable source and unexpected reparse traversal are first-class policy errors, not generic “failed” toasts.

Future physical apply region:

- disabled by default;
- requires a fresh plan token/identity;
- repeats exact source/target, ownership, expected digest and rollback meaning;
- cannot degrade to direct file copy/move;
- recover/rollback reflect durable M03 transaction states;
- only becomes enabled after explicit typed adapters and tests are owned by a later implementation step.

## 10. System/source health

System merges Sources & Health with Runtime to prevent navigation sprawl.

Top health strip:

- public route target: 8943 current accepted service;
- rollback target: 8942;
- current Skill/variant/non-selectable/invalid/explicit-file counts;
- SQLite schema/parity/integrity/FK;
- active deployment transaction count;
- route/identity freshness.

Source table:

- source_class;
- root/path;
- authority tier;
- selectable;
- active;
- selected/variant contribution when a read model exists.

A degraded/stale identity warning appears if public selected identity disagrees with fresh validation/canonical state or if route health is not the accepted state. No OAuth token, cookie, session secret or credential material is ever displayed.

## 11. Loading, empty, error and degraded states

- **Loading:** metadata skeletons and stable table geometry; body tab has a separate on-demand loading state.
- **No search matches:** preserve active filters and offer “Clear filters”.
- **No organization metadata:** explanatory empty state with “Create category/tag”; this is the current canonical DB state.
- **No workflows/runs:** onboarding empty states, distinct from request failure.
- **Read error:** preserve last stable view where safe; expose retry for idempotent reads.
- **Mutation error:** never blind-retry. Refresh authoritative state, preserve unsaved local edits and surface typed error.
- **Degraded truth:** persistent banner; disable mutations that depend on untrusted parity/route state while allowing inspection/export/copy.
- **Invalid discovery input:** show as Discovery Issue with path/error; do not mint or imply a canonical Skill.

## 12. Deep links and routing contract

Suggested route semantics:

- `/` Overview
- `/skills?q=&source=&authority=&status=&category=&tag=`
- `/skills/:skill_id`
- `/skills/:skill_id/variants/:variant_id`
- `/workflows`
- `/workflows/:workflow_id`
- `/workflows/:workflow_id/new-version`
- `/runs?status=&workflow=&skill=`
- `/runs/:run_id`
- `/deployments`
- `/deployments/plan?skill_id=`
- `/system/sources`
- `/system/health`

Client routes are presentation only; backend identifiers remain canonical IDs.

## 13. Accessibility and keyboard expectations

- Full keyboard access to tables, tabs, dialogs, menus and stage editor.
- Visible focus ring with WCAG-compliant contrast.
- Semantic table headers and row labels.
- Status never conveyed by color alone; text/icon labels accompany color.
- `/` focuses global search when not in a text editor.
- `Ctrl+K` may open a command/search palette.
- Enter opens selected row; Escape closes transient panels.
- Destructive or future physical actions never get single-keystroke shortcuts.
- Dialog focus is trapped and restored.
- Code/body views support wrapping and keyboard scrolling.
- Reduced-motion preference is honored.

## 14. M05 non-goals preserved

No frontend source, Web API, dev server, visual QA, production packaging, desktop launcher/reboot integration, mass migration, arbitrary filesystem manager, generic shell surface or physical apply was implemented in M05.
