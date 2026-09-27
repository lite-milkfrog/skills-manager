# SCP-M05 -> M06 Implementation Matrix

PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922

## 1. Contract rule

M06 must implement against the existing services and the exact M04 public adapters. A row marked **DESIGN_READY_BACKEND_GAP** requires a minimal typed adapter/read model; it does not authorize a second scanner, workflow engine, executor, database or raw shell surface.

Mutation classes follow M05-PRODUCT-SPEC.md.

## 2. Existing public tool mapping

| UI surface/action | Existing M04 tool/service | Class | Confirmation | Expected states |
|---|---|---:|---|---|
| Registry health summary | `skills_status` | R0 | none | loading / healthy / degraded / error |
| Compact Skill search | `skills_search(query,limit)` | R0 | none | results / no matches / error |
| Initial compact selected-Skill sample | `skills_list(limit<=200)` | R0 | none | results / empty / error |
| Selected Skill detail + body + variants | `skills_get(name)` | R0 | none | loaded / unknown skill / read error |
| Validate selected Skill | `skills_validate(name)` | R0 | none | valid / invalid / read error |
| Validate explicit known local variant path | `skills_validate(path)` | R0 | none | valid / invalid / path error |
| Evaluate Skill for task query | `skills_evaluate(name,query)` | R0 | none | ranked/result / validation error |
| Create/validate unsaved workflow version | `workflow_create(spec,dry_run=true)` | R0 preview | none | normalized plan / typed validation error / duplicate |
| Persist a new workflow version | `workflow_create(spec,dry_run=false)` | R1 | explicit Save/Create click | created / validation error / duplicate |
| Deterministic stored workflow plan | `workflow_plan(workflow_id,context)` | R0 | none | plan / unknown workflow / binding error |
| Create durable planned run | `run_create(workflow_id,context,run_key?)` | R2 | explicit action | planned / validation error |
| Inspect one run | `run_get(run_id)` | R0 | none | snapshot / unknown run |
| Start planned run | `run_start(run_id)` | R2 | explicit action | active / typed illegal transition |
| Block current stage | `run_block(run_id,reason)` | R2 | reason required | blocked / typed illegal transition |
| Add run evidence | `run_evidence_add(run_id,kind,payload,evidence_key?)` | R2 | payload preview | updated snapshot / validation error |
| Resume blocked run | `run_resume(run_id)` | R2 | explicit action | active / typed illegal transition / evidence requirement |
| Succeed current stage | `run_succeed(run_id,gate_result?)` | R2 | contextual explicit action | next stage / completed / typed illegal transition |
| Deployment/relocation dry-run | `deployment_plan(skill_id,operation,source_path?,target_path?)` | R3 | none; dry-run banner | plan / typed M03 policy error |

## 3. DESIGN_READY_BACKEND_GAP — scalable/read surfaces

| UI need | Minimal typed M06 adapter | Reuse/owner | Class | Notes |
|---|---|---|---:|---|
| Full 2321-Skill paging/filtering | `skills_page({query,facets,sort,cursor,limit})` | M01 Registry metadata only | R0 | Must not rescan or load bodies. Existing `skills_list` lacks offset/cursor/facets. |
| Invalid discovery issue list | `discovery_issues_page({cursor,limit,filters})` | M01 snapshot invalid records | R0 | Invalid inputs stay separate from canonical Skills. |
| Full source list/authority health | `sources_list()` | `ManagementService.list_sources` + current snapshot | R0 | No secrets. |
| Runtime/DB health | `runtime_health()` | existing route observation + RegistryStore/DB integrity/parity read | R0 | Typed fields for public route/current/rollback service, schema/parity/FK/active tx. No arbitrary process control. |
| Workflow list | `workflow_list({cursor,limit,name})` | SQLite Workflow tables | R0 | No new workflow model. |
| Workflow detail/spec | `workflow_get(workflow_id)` | existing `WorkflowService.get_workflow` | R0 | Required for inspect and new-version copy. |
| Run list/filter | `run_list({status,workflow_id,skill_id,cursor,limit})` | existing Run/SQLite tables | R0 | No executor logic. |
| Deployment transaction history | `deployment_transactions_list({state,skill_id,cursor,limit})` | M03 journal | R0 | Read-only. |
| Managed locations | `managed_locations_list({skill_id?,cursor,limit})` | M03 `managed_paths` | R0 | Expose ownership/digest/state only. |
| Global audit | `audit_list({entity_type,entity_id,action,cursor,limit})` | SQLite audit_log | R0 | Run-specific audit already comes from `run_get`. |

## 4. DESIGN_READY_BACKEND_GAP — organization/context metadata

The service layer already contains some write primitives but M04 deliberately does not expose them. M06 must add narrow typed adapters, not direct SQL from the frontend.

| UI action | Minimal backend contract | Existing owner | Class | Confirmation |
|---|---|---|---:|---|
| List categories | `categories_list()` | add read method to ManagementService | R0 | none |
| Create/update category | `category_upsert(name,description,dry_run?)` | `ManagementService.upsert_category` | R1 | none |
| Delete category | `category_delete(category_id,dry_run?)` | `ManagementService.delete_category` | R1 | destructive metadata confirm |
| List tags | `tags_list()` | add read method to ManagementService | R0 | none |
| Create/update tag | `tag_upsert(name,dry_run?)` | `ManagementService.upsert_tag` | R1 | none |
| Delete tag | `tag_delete(tag_id,dry_run?)` | `ManagementService.delete_tag` | R1 | destructive metadata confirm |
| Read one Skill organization | `skill_organization_get(skill_id)` | Management tables | R0 | none |
| Bind category | `skill_category_bind(skill_id,category_id,dry_run?)` | `ManagementService.bind_category` | R1 | none |
| Unbind category | `skill_category_unbind(skill_id,category_id,dry_run?)` | **service method gap** | R1 | none |
| Bind tag | `skill_tag_bind(skill_id,tag_id,dry_run?)` | `ManagementService.bind_tag` | R1 | none |
| Unbind tag | `skill_tag_unbind(skill_id,tag_id,dry_run?)` | **service method gap** | R1 | none |
| Context/workspace list | `workspaces_list()` | Management tables | R0 | none |
| Agent list | `agents_list()` | Management tables | R0 | none |
| Workspace/agent metadata edits | narrow typed upsert adapters | existing ManagementService upserts | R1 | explicit save |

M06 may choose to defer organization delete/unbind UI until the corresponding typed methods exist; it must not fake unbind by direct frontend database access.

## 5. DESIGN_READY_BACKEND_GAP — local Explorer action

Required contract: `skill_open_folder({skill_id, variant_id?})`.

Rules:

1. Resolve skill_id/variant_id through canonical Discovery/SQLite identity.
2. Resolve the containing local directory server-side.
3. Confirm record is current/known and the path is local.
4. Invoke one allowlisted Windows Explorer-open operation.
5. Return `{opened:true, path:<resolved path>}` or a typed path/not-found/not-local error.
6. Do not accept executable name, command line, flags, PowerShell, cmd, arbitrary URL or generic shell payload.

Class: L1 LOCAL_UI_SIDE_EFFECT. No confirmation.

## 6. Explicitly disabled physical backend gap

M03 internally owns `begin/apply/recover/rollback`, but M04 exposes only `deployment_plan`. Therefore these UI actions remain disabled:

- Apply deployment
- Apply update
- Apply relocation
- Undeploy
- Recover transaction
- Roll back transaction

Status: **DESIGN_READY_BACKEND_GAP / NOT ENABLED**.

Any later adapter must:

- accept a previously validated typed plan/transaction identity, never an arbitrary file operation;
- revalidate current source/target/digests/ownership;
- call M03 transaction semantics;
- expose durable state and verification evidence;
- preserve reparse/protected-target/collision/drift checks;
- support explicit recovery/rollback states;
- have dedicated tests and confirmation UX.

M06 must not implement these by shell, fs.rename/copy, Explorer automation or direct ad-hoc filesystem code.

## 7. Explicit non-features

- In-place overwrite of a stored workflow version: **NOT SUPPORTED BY MODEL**. Create a new version instead.
- Editable node-graph schema: **NOT SUPPORTED**. Visual flow is derived from ordered stages.
- Run fail button: **NOT PUBLIC IN M04**. Inspect failed runs, but do not enable failure mutation without a typed adapter.
- Arbitrary open path/terminal/shell: **FORBIDDEN**.
- Promote historical variant by UI preference: **FORBIDDEN**; M01 resolver remains authority.
- Generic file move: **FORBIDDEN**; relocation belongs to M03.
- Direct browser access to SQLite: **FORBIDDEN**.

## 8. M06 completion expectation

Implementation is complete only when every enabled control has one of:

1. an existing M04 typed adapter;
2. a newly implemented minimal typed adapter listed above and backed by the existing service/truth owner;
3. client-only behavior with no mutation (routing, copy path, local form state).

Anything else stays visibly disabled with its reason.
