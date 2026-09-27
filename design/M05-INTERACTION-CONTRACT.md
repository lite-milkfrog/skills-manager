# SCP-M05 Interaction Contract

PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922

## 1. Interaction rule

Every action belongs to an explicit truth owner and mutation class. The frontend never writes SQLite directly, scans the filesystem independently, moves files directly, or infers a legal Run transition from UI state alone.

## 2. Skill interactions

### Search/list

- Debounce query input modestly.
- Cancel superseded reads.
- Do not preload SKILL.md.
- Filters update URL state.
- Selecting a row navigates to a stable canonical skill_id route.

### Selected vs variants

“Selected” badge means the M01 resolver selected that variant. Adjacent fields always expose source class and authority. Alternate selectable and non-selectable/historical variants have separate groups.

Historical archive variants use a muted “Non-selectable / historical” label. They are inspectable but cannot be silently promoted by the frontend.

### Body

Opening Body triggers a lazy full get. Body failure does not make list metadata disappear. Display digest/path alongside the body so the user knows which selected source was read.

### Validation/evaluation

Validation is an explicit action and shows exact backend findings. Evaluation always includes the user-entered task query so a result is not mistaken for global quality ranking.

### Organization

Add/remove category/tag is metadata-only. The confirmation/help text states “File path will not change.” If organization mutation fails, refetch organization metadata only.

### Open in Explorer

The frontend sends an identity reference, not a command line:

- skill_id;
- optional variant_id;
- intent = containing_folder.

Backend resolves current path, verifies it maps to the requested canonical record and is a local filesystem location, then invokes an allowlisted Explorer-open implementation. No arbitrary executable, flags or shell string may be accepted.

Backend status: DESIGN_READY_BACKEND_GAP.

## 3. Workflow interactions

### Inspect

Stored workflow versions are read-only. Version switcher changes route/detail without overwriting another version.

### Create new version

1. User chooses Create new version.
2. Existing workflow spec is loaded when available.
3. UI increments/proposes version but user-visible version remains explicit.
4. Local editor state uses exactly the WorkflowService field names/semantics.
5. “Validate preview” calls workflow_create with dry_run=true.
6. UI shows normalized stage order and errors.
7. “Create version” calls workflow_create with dry_run=false exactly once after explicit click.
8. On success navigate to the returned workflow_id.
9. Duplicate ID/version error never triggers an automatic increment-and-retry without user review.

### Stage reorder

Drag/drop and keyboard move controls only change local editor ordinal ordering. Saving sends the resulting ordered stages in one workflow spec. There is no standalone persisted “move stage” operation.

### Skill picker

Uses canonical Skill metadata search. The stored value is canonical skill_id. Display name/source hints are presentation only.

### Visual preview

The right-side path preview is generated from the same local normalized spec or workflow_plan response. It never stores nodes/edges separately.

## 4. Run interactions

### Create/start

Create returns a planned durable run. Start is a separate transition. The UI may offer “Create and start” as a two-step orchestrated command only if it visibly handles partial success: if creation succeeds but start fails, navigate to the planned run and surface the error rather than creating another run.

### Block

Block requires a non-empty explicit reason. The reason is persisted verbatim as run state; UI does not silently rewrite it.

### Evidence

Evidence add shows kind and payload preview before submission. Repeated submission should use evidence_key when supported to make caller intent explicit.

### Resume

Client enables resume only for a blocked run with evidence present, but server remains authoritative. A TransitionError produces:

- no automatic retry;
- a state refresh;
- error banner retaining the typed reason;
- disabled stale action if refreshed state makes it illegal.

### Succeed

Only shown for an active/running current stage. Gate result is visible in the confirmation/action panel. Server may advance to another stage or terminal complete; UI uses returned snapshot rather than guessing.

### Failed runs

Failed status and failure evidence are fully inspectable. M04 exposes no public run_fail action, so M06 must not expose an enabled “Fail stage” control unless a typed adapter is explicitly added.

## 5. Deployment interactions

### Plan first

The only enabled physical-management action in the accepted public contract is previewing a deployment plan.

Plan request:

- skill_id;
- operation;
- optional source_path;
- optional target_path.

Result panel presents plan_id and transaction_id as identifiers, not proof that a physical transaction was executed.

### Policy errors

Map typed policy errors to focused explanations while preserving the original code/string:

- protected-target;
- destination-collision;
- source-drift-from-selected-variant;
- managed-path-drift;
- historical/nonselectable ownership rejection;
- target-outside-managed-roots;
- unexpected reparse/symlink/junction safety rejection;
- unknown operation / missing target.

Never provide a “force anyway” button.

### Future physical apply

Disabled until a public owned backend contract exists. Required future sequence:

`fresh dry-run -> plan identity/digest review -> explicit confirmation -> M03 begin/apply -> verify -> committed OR recover/rollback`.

The frontend may not substitute copy/move/delete APIs.

## 6. Confirmation policy

- R0: none.
- R1 additive metadata: no modal; optimistic UI only if rollback/refetch is safe.
- R1 destructive category/tag deletion: modal summarizing affected metadata relations; no filesystem language.
- R2: direct explicit button; block requires reason; resume/succeed contextual; no repeated confirmation spam.
- R3 dry-run: no modal; high-risk preview styling only.
- R4 future physical apply: mandatory confirmation with exact source/target/ownership/digests/operation and rollback statement.
- L1 Explorer open: no confirmation.

## 7. Error handling

### Read failures

Show scoped error and retry. Do not erase other already-loaded panes.

### Mutation failures

- Preserve unsaved local form state.
- Do not blindly retry.
- Refetch authoritative entity after conflict/transition errors.
- Display backend error code/string in expandable technical detail.
- If parity/integrity/runtime freshness is degraded, disable mutations dependent on trustworthy canonical state.

### Stale responses

Every detail mutation should refresh from returned authoritative response or a fresh get. Long-running list/search requests are cancelable. A late search response must not overwrite a newer query.

## 8. Empty states

- Skills empty: abnormal system state; point to System health.
- Skill search empty: “No matches” + clear filters.
- Categories/tags empty: current normal first-use state; explain metadata organization and offer create action.
- Workflows empty: offer Create Workflow.
- Runs empty: explain runs originate from stored workflows.
- Deployment transactions empty: explain dry-run plans do not create transaction rows.
- Invalid discovery issues empty: positive “No discovery issues” state.

## 9. Accessibility

- All icon-only actions have accessible labels.
- Status includes text.
- Table row action menus work by keyboard.
- Drag stage reorder has keyboard alternatives.
- Focus is restored after dialogs.
- Error summary links to invalid fields.
- IDs/paths can wrap or horizontally scroll without clipping actionable content.
