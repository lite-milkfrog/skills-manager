# SCP-M05 Information Architecture

PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922

## 1. Navigation decision

Use six primary destinations:

1. **Overview**
2. **Skills**
3. **Workflows**
4. **Runs**
5. **Deployments**
6. **System**

This is intentionally smaller than a one-table-per-database navigation.

### Merged sections

- **Categories / Tags** are not top-level. They are Skill organization primitives and live under Skills: Organization plus filter/manager surfaces.
- **Sources / Health** and **Settings / Runtime** merge into System because they describe authority and operating truth rather than daily content objects.
- **Deployment / Locations** remain together because location changes are physical-risk operations and must not look like ordinary metadata organization.
- Workspace/Agent associations appear contextually in Skill/Workflow relations and may gain a System subview once list/read adapters exist.

## 2. App shell

Desktop layout:

- 220–248 px collapsible left navigation;
- top command/search bar with global search and current health indicator;
- main content region;
- optional right inspector for quick row inspection;
- full route for durable detail/deep linking.

Breadcrumbs are shown on detail/editor routes. Browser back/forward must preserve route and filter query state.

## 3. Overview

Purpose: operational orientation, not decorative analytics.

Blocks:

- Health summary: public route/current service, parity/integrity, active transaction count.
- Inventory: selected Skills / variants / non-selectable / invalid.
- Runs: counts by current status once read adapter exists, plus recently changed runs.
- Workflows: recent versions.
- Discovery issues: invalid/degraded count.
- Quick actions: Search Skills, Create Workflow Version, Inspect Runs, Plan Deployment.

No body content or huge charts load on Overview.

## 4. Skills

### Skills index

Default route: `/skills`.

Persistent elements:

- search field;
- facet row;
- compact virtualized/paginated table;
- result count;
- sort control;
- saved URL state;
- multi-select only for metadata organization operations.

Row opens `/skills/:skill_id`.

### Skill detail

Header:

- display name;
- canonical skill_id secondary mono label;
- health;
- selected source badge;
- authority tier;
- variant count.

Tabs:

- Overview
- Variants
- Body
- Validation
- Organization
- Relations

### Discovery Issues

Accessible from a Skills filter and System health. Invalid discovered files remain separate issue records rather than fake Skill rows.

## 5. Workflows

### Workflow index

Default route: `/workflows`.

Columns:

- name;
- version;
- workflow_id;
- stage count;
- key Skill bindings summary;
- active flag;
- created/updated when available.

Group versions under a workflow name in the UI without inventing a new persisted workflow-family entity.

### Workflow detail

- Summary
- Definition
- Plan Preview
- Related Runs

Stored definition is read-only. Primary action is **Create new version**.

### New-version editor

Main structured stage list + right deterministic visual summary. All fields map directly to the existing WorkflowService shape. No editable graph schema.

## 6. Runs

### Run index

Default route: `/runs`.

Columns:

- status;
- task/context summary;
- workflow + version;
- current stage;
- resolved Skill summary;
- updated time.

Filters: status, workflow, Skill, stage/time when backed by adapter.

### Run detail

Route `/runs/:run_id`.

Order:

1. Status/task/workflow header.
2. Ordered stage rail.
3. Current/selected stage facts.
4. Evidence timeline.
5. Audit timeline.
6. Terminal result.

Blocked banner appears above the stage rail.

## 7. Deployments

### Plan Builder

Route `/deployments/plan`.

Sections:

1. Skill identity.
2. Operation.
3. Source/target.
4. Preview.
5. Preconditions/policy findings.
6. Disabled future physical apply area.

### Locations & Transactions

Read-only design target:

- managed paths;
- ownership class;
- digest;
- transaction state;
- source/target;
- rollback/recovery state.

This surface needs M06 typed read adapters.

## 8. System

Subnavigation:

- **Health**
- **Sources**
- **Organization** (administrative category/tag definitions, if needed)
- **Contexts** (workspace/agent associations once adapters exist)

Health shows route/service identity, Discovery counts, SQLite parity/integrity/FK and deployment activity. Sources shows authority roots/classes. No secrets are displayed.

## 9. Search architecture

Global search is an entity launcher, not an eager full-text Skill body index.

Order:

1. canonical Skill metadata;
2. workflows;
3. runs by stable ID/context if adapter supports it;
4. commands/navigation.

Skill body search is out of M05 unless a future backend explicitly indexes bodies. Current skills_search remains metadata/task/path oriented.

## 10. Large inventory behavior

- Page/cursor-backed table data is required in M06; current `skills_list(limit<=200)` alone is insufficient for a 2321-entry full inventory.
- Virtualization is a rendering optimization, not a substitute for backend paging.
- Filter/sort state belongs in URL query parameters.
- Table rows contain compact metadata only.
- Full body/variant payloads are fetched after navigation/explicit expansion.
- Avoid loading all 6630 variant payloads into the index route.

## 11. Hierarchy rules

Skill hierarchy:

`canonical skill_id -> selected variant + alternate variants -> source class/root`

Workflow hierarchy:

`workflow name/version -> ordered stage -> binding -> canonical skill_id`

Run hierarchy:

`run -> workflow/version -> run stage -> resolved binding/evidence/audit`

Deployment hierarchy:

`plan/transaction -> operation -> source/target -> preconditions -> steps/state`

The UI must not flatten these into unrelated CRUD tables.
