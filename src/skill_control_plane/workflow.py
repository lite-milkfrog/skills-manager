from __future__ import annotations

from typing import Any

from .management import ValidationError
from .search_terms import normalized_search_terms
from .storage import ControlPlaneDB, utc_now
from .utils import condition_matches, json_text, json_value, stable_id


class WorkflowService:
    def __init__(self, db: ControlPlaneDB) -> None:
        self.db = db
        self.db.migrate()

    def _require_skill(self, conn, skill_id: str) -> None:
        if (
            conn.execute(
                "SELECT 1 FROM skills WHERE skill_id=? AND active=1", (skill_id,)
            ).fetchone()
            is None
        ):
            raise ValidationError(f"unknown-skill-id:{skill_id}")

    def create_workflow(self, spec: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        name = str(spec.get("name", "")).strip()
        version = int(spec.get("version", 1))
        description = str(spec.get("description", ""))
        stages = spec.get("stages", [])
        if not name:
            raise ValidationError("workflow-name-required")
        if version < 1:
            raise ValidationError("workflow-version-invalid")
        if not isinstance(stages, list) or not stages:
            raise ValidationError("workflow-stages-required")
        workflow_id = stable_id("wf", name, version)
        normalized: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for ordinal, raw in enumerate(stages):
            if not isinstance(raw, dict):
                raise ValidationError("workflow-stage-invalid")
            key = str(raw.get("key", "")).strip()
            if not key or key in seen_keys:
                raise ValidationError(f"workflow-stage-key-invalid:{key}")
            seen_keys.add(key)
            stage_id = stable_id("stage", workflow_id, key)
            bindings: list[dict[str, Any]] = []
            raw_bindings = raw.get("bindings", [])
            if not isinstance(raw_bindings, list):
                raise ValidationError(f"workflow-bindings-invalid:{key}")
            binding_keys: set[str] = set()
            for bind_ordinal, binding in enumerate(raw_bindings):
                if not isinstance(binding, dict):
                    raise ValidationError(f"workflow-binding-invalid:{key}")
                binding_key = str(binding.get("key", "")).strip()
                skill_id = str(binding.get("skill_id", "")).strip().casefold()
                binding_type = str(binding.get("type", "required")).strip().casefold()
                if not binding_key or binding_key in binding_keys:
                    raise ValidationError(f"workflow-binding-key-invalid:{binding_key}")
                if binding_type not in {"required", "optional", "conditional"}:
                    raise ValidationError(f"workflow-binding-type-invalid:{binding_type}")
                binding_keys.add(binding_key)
                bindings.append(
                    {
                        "binding_id": stable_id("bind", stage_id, binding_key),
                        "key": binding_key,
                        "skill_id": skill_id,
                        "type": binding_type,
                        "condition": binding.get("condition") or {},
                        "fallback_skill_id": (
                            str(binding["fallback_skill_id"]).casefold()
                            if binding.get("fallback_skill_id")
                            else None
                        ),
                        "ordinal": bind_ordinal,
                    }
                )
            normalized.append(
                {
                    "stage_id": stage_id,
                    "key": key,
                    "title": str(raw.get("title", "")).strip(),
                    "description": str(raw.get("description", "")).strip(),
                    "instructions": str(raw.get("instructions", "")).strip(),
                    "expected_output": str(raw.get("expected_output", "")).strip(),
                    "completion_criteria": str(raw.get("completion_criteria", "")).strip(),
                    "ordinal": ordinal,
                    "condition": raw.get("condition") or {},
                    "success_gate": raw.get("success_gate") or {},
                    "failure_gate": raw.get("failure_gate") or {},
                    "retry_limit": int(raw.get("retry_limit", 0)),
                    "loop_limit": int(raw.get("loop_limit", 0)),
                    "loop_stop_condition": raw.get("loop_stop_condition") or {},
                    "fallback_stage_key": raw.get("fallback_stage"),
                    "bindings": bindings,
                }
            )
        key_to_id = {stage["key"]: stage["stage_id"] for stage in normalized}
        for stage in normalized:
            if stage["retry_limit"] < 0 or stage["loop_limit"] < 0:
                raise ValidationError(f"workflow-bounds-invalid:{stage['key']}")
            fallback_key = stage["fallback_stage_key"]
            if fallback_key is not None and str(fallback_key) not in key_to_id:
                raise ValidationError(f"unknown-fallback-stage:{fallback_key}")

        plan = {
            "workflow_id": workflow_id,
            "name": name,
            "version": version,
            "description": description,
            "stages": normalized,
        }
        if dry_run:
            if (
                self.db.connection.execute(
                    "SELECT 1 FROM workflows WHERE workflow_id=?", (workflow_id,)
                ).fetchone()
                is not None
            ):
                raise ValidationError(f"workflow-already-exists:{workflow_id}")
            for stage in normalized:
                for binding in stage["bindings"]:
                    self._require_skill(self.db.connection, binding["skill_id"])
                    if binding["fallback_skill_id"]:
                        self._require_skill(
                            self.db.connection,
                            binding["fallback_skill_id"],
                        )
            return {"dry_run": True, "action": "workflow.create", "plan": plan}

        now = utc_now()
        with self.db.transaction() as conn:
            if (
                conn.execute(
                    "SELECT 1 FROM workflows WHERE workflow_id=?", (workflow_id,)
                ).fetchone()
                is not None
            ):
                raise ValidationError(f"workflow-already-exists:{workflow_id}")
            for stage in normalized:
                for binding in stage["bindings"]:
                    self._require_skill(conn, binding["skill_id"])
                    if binding["fallback_skill_id"]:
                        self._require_skill(conn, binding["fallback_skill_id"])
            conn.execute(
                """
                INSERT INTO workflows(
                    workflow_id,name,version,description,active,created_at,updated_at
                ) VALUES(?,?,?,?,1,?,?)
                """,
                (workflow_id, name, version, description, now, now),
            )
            for stage in normalized:
                conn.execute(
                    """
                    INSERT INTO workflow_stages(
                        stage_id,workflow_id,stage_key,title,description,instructions,
                        expected_output,completion_criteria,ordinal,condition_json,
                        success_gate_json,failure_gate_json,retry_limit,loop_limit,
                        loop_stop_condition_json,fallback_stage_id,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)
                    """,
                    (
                        stage["stage_id"],
                        workflow_id,
                        stage["key"],
                        stage["title"],
                        stage["description"],
                        stage["instructions"],
                        stage["expected_output"],
                        stage["completion_criteria"],
                        stage["ordinal"],
                        json_text(stage["condition"]),
                        json_text(stage["success_gate"]),
                        json_text(stage["failure_gate"]),
                        stage["retry_limit"],
                        stage["loop_limit"],
                        json_text(stage["loop_stop_condition"]),
                        now,
                        now,
                    ),
                )
            for stage in normalized:
                fallback_key = stage["fallback_stage_key"]
                if fallback_key is not None:
                    conn.execute(
                        "UPDATE workflow_stages SET fallback_stage_id=? WHERE stage_id=?",
                        (key_to_id[str(fallback_key)], stage["stage_id"]),
                    )
                for binding in stage["bindings"]:
                    conn.execute(
                        """
                        INSERT INTO workflow_skill_bindings(
                            binding_id,stage_id,binding_key,skill_id,binding_type,
                            condition_json,fallback_skill_id,ordinal,created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            binding["binding_id"],
                            stage["stage_id"],
                            binding["key"],
                            binding["skill_id"],
                            binding["type"],
                            json_text(binding["condition"]),
                            binding["fallback_skill_id"],
                            binding["ordinal"],
                            now,
                        ),
                    )
            self.db.audit(
                conn,
                "workflow.create",
                "workflow",
                workflow_id,
                {"name": name, "version": version, "stage_count": len(normalized)},
            )
        return plan

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow = self.db.connection.execute(
            "SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,)
        ).fetchone()
        if workflow is None:
            raise ValidationError(f"unknown-workflow-id:{workflow_id}")
        stages: list[dict[str, Any]] = []
        for row in self.db.connection.execute(
            "SELECT * FROM workflow_stages WHERE workflow_id=? ORDER BY ordinal,stage_id",
            (workflow_id,),
        ):
            bindings = [
                {
                    "binding_id": bind["binding_id"],
                    "key": bind["binding_key"],
                    "skill_id": bind["skill_id"],
                    "skill_name": bind["skill_name"],
                    "type": bind["binding_type"],
                    "condition": json_value(bind["condition_json"], {}),
                    "fallback_skill_id": bind["fallback_skill_id"],
                    "fallback_skill_name": bind["fallback_skill_name"],
                    "ordinal": int(bind["ordinal"]),
                }
                for bind in self.db.connection.execute(
                    """
                    SELECT b.*,
                           s.name AS skill_name,
                           fs.name AS fallback_skill_name
                    FROM workflow_skill_bindings b
                    LEFT JOIN skills s ON s.skill_id=b.skill_id
                    LEFT JOIN skills fs ON fs.skill_id=b.fallback_skill_id
                    WHERE b.stage_id=?
                    ORDER BY b.ordinal,b.binding_id
                    """,
                    (row["stage_id"],),
                )
            ]
            stages.append(
                {
                    "stage_id": row["stage_id"],
                    "key": row["stage_key"],
                    "title": row["title"],
                    "description": row["description"],
                    "instructions": row["instructions"],
                    "expected_output": row["expected_output"],
                    "completion_criteria": row["completion_criteria"],
                    "ordinal": int(row["ordinal"]),
                    "condition": json_value(row["condition_json"], {}),
                    "success_gate": json_value(row["success_gate_json"], {}),
                    "failure_gate": json_value(row["failure_gate_json"], {}),
                    "retry_limit": int(row["retry_limit"]),
                    "loop_limit": int(row["loop_limit"]),
                    "loop_stop_condition": json_value(row["loop_stop_condition_json"], {}),
                    "fallback_stage_id": row["fallback_stage_id"],
                    "bindings": bindings,
                }
            )
        return {
            "workflow_id": workflow_id,
            "name": workflow["name"],
            "version": int(workflow["version"]),
            "archived": not bool(workflow["active"]),
            "description": workflow["description"],
            "created_at": workflow["created_at"],
            "updated_at": workflow["updated_at"],
            "stages": stages,
        }

    @staticmethod
    def _page(items: list[dict[str, Any]], cursor: int, limit: int) -> dict[str, Any]:
        start = max(0, int(cursor))
        bounded = max(1, min(int(limit), 200))
        page = items[start : start + bounded]
        next_cursor = start + len(page)
        return {
            "items": page,
            "total": len(items),
            "cursor": start,
            "limit": bounded,
            "next_cursor": next_cursor if next_cursor < len(items) else None,
        }

    def list_workflows(
        self, *, cursor: int = 0, limit: int = 50, include_archived: bool = False
    ) -> dict[str, Any]:
        rows = self.db.connection.execute(
            """
            SELECT w.workflow_id,w.name,w.version,w.description,w.active,
                   w.created_at,w.updated_at,
                   COUNT(DISTINCT s.stage_id) AS stage_count,
                   COUNT(DISTINCT b.binding_id) AS binding_count
            FROM workflows w
            LEFT JOIN workflow_stages s ON s.workflow_id=w.workflow_id
            LEFT JOIN workflow_skill_bindings b ON b.stage_id=s.stage_id
            WHERE (w.active=1 OR ?=1)
            GROUP BY w.workflow_id
            ORDER BY w.name COLLATE NOCASE,w.version DESC,w.workflow_id
            """,
            (int(include_archived),),
        ).fetchall()
        items = [
            {
                "workflow_id": row["workflow_id"],
                "name": row["name"],
                "description": row["description"],
                "version": int(row["version"]),
                "archived": not bool(row["active"]),
                "stage_count": int(row["stage_count"]),
                "binding_count": int(row["binding_count"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return self._page(items, cursor, limit)

    def workflow_usage(self, workflow_id: str) -> dict[str, Any]:
        workflow = self.get_workflow(workflow_id)
        conn = self.db.connection
        run_rows = conn.execute(
            "SELECT status,COUNT(*) AS count FROM workflow_runs "
            "WHERE workflow_id=? GROUP BY status",
            (workflow_id,),
        ).fetchall()
        runs = {row["status"]: int(row["count"]) for row in run_rows}
        references = int(conn.execute(
            "SELECT COUNT(*) FROM workflow_stages WHERE fallback_stage_id IN "
            "(SELECT stage_id FROM workflow_stages WHERE workflow_id=?) "
            "AND workflow_id<>?",
            (workflow_id, workflow_id),
        ).fetchone()[0])
        # Fallback references are the only cross-workflow schema reference today.
        return {
            "workflow_id": workflow_id,
            "archived": workflow["archived"],
            "runs": runs,
            "run_count": sum(runs.values()),
            "reference_count": references,
            "can_delete": workflow["archived"] and not runs and references == 0,
        }

    def _set_archived(self, workflow_id: str, archived: bool) -> dict[str, Any]:
        self.get_workflow(workflow_id)
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE workflows SET active=?,updated_at=? WHERE workflow_id=?",
                (int(not archived), now, workflow_id),
            )
            self.db.audit(conn, "workflow.archive" if archived else "workflow.restore",
                          "workflow", workflow_id, {"archived": archived})
        return self.get_workflow(workflow_id)

    def archive_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._set_archived(workflow_id, True)

    def restore_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._set_archived(workflow_id, False)

    def archive_workflow_family(self, name: str) -> dict[str, Any]:
        rows = self.db.connection.execute(
            "SELECT workflow_id FROM workflows WHERE name=? COLLATE NOCASE", (name,)
        ).fetchall()
        if not rows:
            raise ValidationError(f"unknown-workflow-name:{name}")
        ids = [row["workflow_id"] for row in rows]
        now = utc_now()
        with self.db.transaction() as conn:
            conn.executemany(
                "UPDATE workflows SET active=0,updated_at=? WHERE workflow_id=?",
                [(now, workflow_id) for workflow_id in ids],
            )
            self.db.audit(conn, "workflow.family.archive", "workflow-family", name,
                          {"workflow_ids": ids})
        return {"name": name, "workflow_ids": ids, "archived": True}

    def delete_workflow_permanently(self, workflow_id: str) -> dict[str, Any]:
        usage = self.workflow_usage(workflow_id)
        if not usage["can_delete"]:
            raise ValidationError("workflow-delete-requires-archived-zero-run-no-reference")
        with self.db.transaction() as conn:
            # Recheck under the write transaction, so a concurrent Run cannot race deletion.
            row = conn.execute(
                "SELECT active FROM workflows WHERE workflow_id=?", (workflow_id,)
            ).fetchone()
            if row is None or row["active"] or conn.execute(
                "SELECT 1 FROM workflow_runs WHERE workflow_id=?", (workflow_id,)
            ).fetchone() or conn.execute(
                "SELECT 1 FROM workflow_stages WHERE fallback_stage_id IN "
                "(SELECT stage_id FROM workflow_stages WHERE workflow_id=?) "
                "AND workflow_id<>?", (workflow_id, workflow_id),
            ).fetchone():
                raise ValidationError("workflow-delete-not-allowed")
            conn.execute("DELETE FROM workflows WHERE workflow_id=?", (workflow_id,))
            self.db.audit(conn, "workflow.delete", "workflow", workflow_id,
                          {"name": usage.get("name"), "permanent": True})
        return {"workflow_id": workflow_id, "deleted": True}

    def search_workflows(
        self,
        query: str,
        *,
        cursor: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        terms = normalized_search_terms(query)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for item in self.list_workflows(cursor=0, limit=200)["items"]:
            workflow = self.get_workflow(str(item["workflow_id"]))
            stage_labels: list[str] = []
            for stage in workflow["stages"]:
                stage_labels.extend(
                    str(value)
                    for value in (
                        stage.get("key"),
                        stage.get("title"),
                        stage.get("description"),
                        stage.get("instructions"),
                        stage.get("expected_output"),
                        stage.get("completion_criteria"),
                    )
                    if value
                )
            binding_labels: list[str] = []
            for stage in workflow["stages"]:
                for binding in stage["bindings"]:
                    binding_labels.extend(
                        value
                        for value in (
                            str(binding.get("skill_id") or ""),
                            str(binding.get("skill_name") or ""),
                            str(binding.get("key") or ""),
                        )
                        if value
                    )
            name = str(item["name"])
            description = str(item.get("description") or "")
            score = 0
            for term in terms:
                if term in name.casefold():
                    score += 12
                if term in description.casefold():
                    score += 6
                if any(term in label.casefold() for label in stage_labels):
                    score += 4
                if any(term in label.casefold() for label in binding_labels):
                    score += 8
            if not terms or score:
                scored.append(
                    (
                        score,
                        name.casefold(),
                        {
                            **item,
                            "matched_stage_labels": stage_labels,
                            "matched_skill_labels": sorted(set(binding_labels)),
                        },
                    )
                )
        scored.sort(key=lambda row: (-row[0], row[1], str(row[2]["workflow_id"])))
        return self._page([row[2] for row in scored], cursor, limit)

    def prompt(
        self,
        workflow_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow = self.get_workflow(workflow_id)
        plan = self.plan(workflow_id, context)
        lines = [
            f"# Agent Workflow: {workflow['name']} v{workflow['version']}",
            "",
            workflow["description"] or "Execute the stored workflow in canonical stage order.",
            "",
            "## Recursive capability contract",
            "- Treat each bound Skill as a capability entry point, not as an atomic prompt token.",
            "- For every selected Skill, load the complete canonical SKILL.md before execution.",
            (
                "- If SKILL.md is a Router, Composite, index, dispatch layer, or "
                "Agent/tool Skill, recursively follow its explicit references, "
                "routing.md, routes.md, references/, workflows/, scripts/, assets/, "
                "and child Skills until executable capability instructions are reached."
            ),
            (
                "- Preserve the Skill's internal orchestration. The outer Workflow "
                "controls outer stage order only; do not flatten or replace a nested "
                "Skill workflow unless this Workflow explicitly overrides that internal step."
            ),
            (
                "- Treat each stage's title, purpose, Agent instructions, expected output, "
                "and completion criteria as the authoritative outer-stage instruction. "
                "A stage may intentionally have no Skill binding; execute its text directly."
            ),
            (
                "- Respect retry, loop, success/failure gate, fallback-stage, and "
                "fallback-Skill metadata exactly as stored."
            ),
            (
                "- Prefer canonical skills_search for discovery and skills_resolve for execution. "
                "skills_resolve must load the complete SKILL.md, required internal resources, "
                "and explicit child Skills within its bounded recursive contract."
            ),
            "",
            "## Ordered stages",
        ]
        by_stage_id = {stage["stage_id"]: stage for stage in workflow["stages"]}
        for planned in plan["stages"]:
            source = by_stage_id[planned["stage_id"]]
            title = source.get("title") or source["key"]
            lines.append(
                f"{planned['ordinal'] + 1}. {title} "
                f"({'enabled' if planned['enabled'] else 'disabled by context'})"
            )
            if source.get("description"):
                lines.append(f"   - Purpose: {source['description']}")
            if source.get("instructions"):
                lines.append(f"   - Agent instructions: {source['instructions']}")
            if source.get("expected_output"):
                lines.append(f"   - Expected output: {source['expected_output']}")
            if source.get("completion_criteria"):
                lines.append(f"   - Completion criteria: {source['completion_criteria']}")
            if source["bindings"]:
                for binding in source["bindings"]:
                    label = binding.get("skill_name") or binding["skill_id"]
                    fallback_label = binding.get("fallback_skill_name") or binding.get(
                        "fallback_skill_id"
                    )
                    fallback = (
                        f"; fallback={fallback_label}" if binding.get("fallback_skill_id") else ""
                    )
                    lines.append(
                        f"   - {binding['key']}: {label} "
                        f"[{binding['skill_id']}; {binding['type']}{fallback}]"
                    )
            else:
                lines.append("   - no Skill binding")
            lines.append(
                f"   - retry={source['retry_limit']}; loop={source['loop_limit']}; "
                f"fallback_stage_id={source['fallback_stage_id'] or 'none'}"
            )
        lines.extend(
            [
                "",
                "## Execution rule",
                (
                    "For each enabled stage, follow its semantic instructions first. Resolve "
                    "each attached binding recursively when present, execute only the "
                    "capabilities required by that stage, collect evidence, evaluate the "
                    "stored gates, then advance according to the canonical Workflow state."
                ),
            ]
        )
        return {
            "workflow_id": workflow_id,
            "name": workflow["name"],
            "version": workflow["version"],
            "prompt": "\n".join(lines),
            "plan": plan,
        }

    def plan(self, workflow_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        workflow = self.get_workflow(workflow_id)
        optional_requested = set(context.get("optional_bindings", []))
        include_optional = bool(context.get("include_optional", False))
        planned_stages: list[dict[str, Any]] = []
        for stage in workflow["stages"]:
            enabled = condition_matches(stage["condition"], context)
            resolved: list[dict[str, Any]] = []
            for binding in stage["bindings"]:
                binding_type = binding["type"]
                include = binding_type == "required"
                if binding_type == "optional":
                    include = (
                        include_optional
                        or binding["key"] in optional_requested
                        or binding["skill_id"] in optional_requested
                    )
                if binding_type == "conditional":
                    include = condition_matches(binding["condition"], context)
                if include:
                    resolved.append(
                        {
                            "binding_id": binding["binding_id"],
                            "binding_key": binding["key"],
                            "skill_id": binding["skill_id"],
                            "binding_type": binding_type,
                            "fallback_skill_id": binding["fallback_skill_id"],
                        }
                    )
            planned_stages.append(
                {
                    "stage_id": stage["stage_id"],
                    "stage_key": stage["key"],
                    "title": stage["title"],
                    "description": stage["description"],
                    "instructions": stage["instructions"],
                    "expected_output": stage["expected_output"],
                    "completion_criteria": stage["completion_criteria"],
                    "ordinal": stage["ordinal"],
                    "enabled": enabled,
                    "resolved_bindings": resolved,
                    "success_gate": stage["success_gate"],
                    "failure_gate": stage["failure_gate"],
                    "retry_limit": stage["retry_limit"],
                    "loop_limit": stage["loop_limit"],
                    "loop_stop_condition": stage["loop_stop_condition"],
                    "fallback_stage_id": stage["fallback_stage_id"],
                }
            )
        return {
            "workflow_id": workflow_id,
            "name": workflow["name"],
            "version": workflow["version"],
            "context": context,
            "stages": planned_stages,
        }
