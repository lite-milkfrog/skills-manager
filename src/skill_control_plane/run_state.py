from __future__ import annotations

from typing import Any

from .management import ValidationError
from .storage import ControlPlaneDB, utc_now
from .utils import condition_matches, json_text, json_value, stable_id
from .workflow import WorkflowService


class TransitionError(RuntimeError):
    pass


class RunService:
    def __init__(self, db: ControlPlaneDB) -> None:
        self.db = db
        self.db.migrate()
        self.workflows = WorkflowService(db)

    def create_run(
        self,
        workflow_id: str,
        context: dict[str, Any] | None = None,
        *,
        run_key: str | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        if self.workflows.get_workflow(workflow_id)["archived"]:
            raise ValidationError("archived-workflow-cannot-start-new-run")
        plan = self.workflows.plan(workflow_id, context)
        run_id = stable_id("run", workflow_id, run_key or utc_now())
        now = utc_now()
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT active FROM workflows WHERE workflow_id=?", (workflow_id,)
            ).fetchone()
            if row is None or not row["active"]:
                raise ValidationError("archived-workflow-cannot-start-new-run")
            if conn.execute("SELECT 1 FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone():
                raise ValidationError(f"run-already-exists:{run_id}")
            conn.execute(
                """
                INSERT INTO workflow_runs(
                    run_id,workflow_id,status,current_stage_id,context_json,
                    terminal_result_json,created_at,updated_at
                ) VALUES(?,?,'planned',NULL,?,NULL,?,?)
                """,
                (run_id, workflow_id, json_text(context), now, now),
            )
            for stage in plan["stages"]:
                status = "pending" if stage["enabled"] else "skipped"
                conn.execute(
                    """
                    INSERT INTO workflow_run_stages(
                        run_stage_id,run_id,stage_id,ordinal,status,resolved_bindings_json,
                        retry_count,loop_count,gate_result_json,blocked_reason,
                        started_at,finished_at,updated_at
                    ) VALUES(?,?,?,?,?,?,0,0,NULL,NULL,NULL,?,?)
                    """,
                    (
                        stable_id("runstage", run_id, stage["stage_id"]),
                        run_id,
                        stage["stage_id"],
                        stage["ordinal"],
                        status,
                        json_text(stage["resolved_bindings"]),
                        now if status == "skipped" else None,
                        now,
                    ),
                )
            self.db.audit(
                conn,
                "run.create",
                "workflow_run",
                run_id,
                {"workflow_id": workflow_id, "context": context},
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.db.connection.execute(
            "SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None:
            raise ValidationError(f"unknown-run-id:{run_id}")
        stages = [
            {
                "run_stage_id": row["run_stage_id"],
                "stage_id": row["stage_id"],
                "ordinal": int(row["ordinal"]),
                "status": row["status"],
                "resolved_bindings": json_value(row["resolved_bindings_json"], []),
                "retry_count": int(row["retry_count"]),
                "loop_count": int(row["loop_count"]),
                "gate_result": json_value(row["gate_result_json"], None),
                "blocked_reason": row["blocked_reason"],
            }
            for row in self.db.connection.execute(
                "SELECT * FROM workflow_run_stages WHERE run_id=? ORDER BY ordinal,run_stage_id",
                (run_id,),
            )
        ]
        return {
            "run_id": run_id,
            "workflow_id": run["workflow_id"],
            "status": run["status"],
            "current_stage_id": run["current_stage_id"],
            "context": json_value(run["context_json"], {}),
            "terminal_result": json_value(run["terminal_result_json"], None),
            "stages": stages,
        }

    def snapshot(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        evidence = [
            {
                "evidence_id": row["evidence_id"],
                "run_stage_id": row["run_stage_id"],
                "kind": row["kind"],
                "payload": json_value(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in self.db.connection.execute(
                """
                SELECT evidence_id,run_stage_id,kind,payload_json,created_at
                FROM workflow_evidence
                WHERE run_id=?
                ORDER BY created_at,evidence_id
                """,
                (run_id,),
            )
        ]
        audit = [
            {
                "audit_id": int(row["audit_id"]),
                "action": row["action"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "payload": json_value(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in self.db.connection.execute(
                """
                SELECT audit_id,action,entity_type,entity_id,payload_json,created_at
                FROM audit_log
                WHERE entity_type='workflow_run' AND entity_id=?
                ORDER BY audit_id
                """,
                (run_id,),
            )
        ]
        return {**run, "evidence": evidence, "audit": audit}

    def _current(self, conn, run_id: str):
        run = conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise ValidationError(f"unknown-run-id:{run_id}")
        stage = None
        if run["current_stage_id"]:
            stage = conn.execute(
                """
                SELECT rs.*, ws.retry_limit, ws.loop_limit, ws.loop_stop_condition_json,
                       ws.fallback_stage_id
                FROM workflow_run_stages rs
                JOIN workflow_stages ws ON ws.stage_id=rs.stage_id
                WHERE rs.run_id=? AND rs.stage_id=?
                """,
                (run_id, run["current_stage_id"]),
            ).fetchone()
        return run, stage

    def start(self, run_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.db.transaction() as conn:
            run, _stage = self._current(conn, run_id)
            if run["status"] != "planned":
                raise TransitionError(f"illegal-run-transition:{run['status']}->active")
            next_stage = conn.execute(
                """
                SELECT * FROM workflow_run_stages
                WHERE run_id=? AND status='pending'
                ORDER BY ordinal,run_stage_id LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if next_stage is None:
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status='completed',terminal_result_json=?,updated_at=?
                    WHERE run_id=?
                    """,
                    (json_text({"result": "no-enabled-stages"}), now, run_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET status='running',started_at=COALESCE(started_at,?),updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (now, now, next_stage["run_stage_id"]),
                )
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status='active',current_stage_id=?,updated_at=?
                    WHERE run_id=?
                    """,
                    (next_stage["stage_id"], now, run_id),
                )
            self.db.audit(conn, "run.start", "workflow_run", run_id, {})
        return self.get_run(run_id)

    def succeed_current(
        self, run_id: str, gate_result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        now = utc_now()
        gate_result = gate_result or {"passed": True}
        with self.db.transaction() as conn:
            run, stage = self._current(conn, run_id)
            if run["status"] != "active" or stage is None or stage["status"] != "running":
                raise TransitionError("illegal-stage-success-transition")
            loop_limit = int(stage["loop_limit"])
            loop_count = int(stage["loop_count"])
            stop_condition = json_value(stage["loop_stop_condition_json"], {})
            context = json_value(run["context_json"], {})
            if (
                loop_limit > 0
                and stop_condition
                and loop_count < loop_limit
                and not condition_matches(stop_condition, context)
            ):
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET loop_count=loop_count+1,gate_result_json=?,updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (json_text(gate_result), now, stage["run_stage_id"]),
                )
                self.db.audit(
                    conn,
                    "run.stage.loop",
                    "workflow_run",
                    run_id,
                    {"stage_id": stage["stage_id"], "loop_count": loop_count + 1},
                )
                return self.get_run(run_id)

            conn.execute(
                """
                UPDATE workflow_run_stages
                SET status='succeeded',gate_result_json=?,blocked_reason=NULL,
                    finished_at=?,updated_at=?
                WHERE run_stage_id=?
                """,
                (json_text(gate_result), now, now, stage["run_stage_id"]),
            )
            next_stage = conn.execute(
                """
                SELECT * FROM workflow_run_stages
                WHERE run_id=? AND status='pending' AND ordinal>?
                ORDER BY ordinal,run_stage_id LIMIT 1
                """,
                (run_id, int(stage["ordinal"])),
            ).fetchone()
            if next_stage is None:
                conn.execute(
                    """
                    UPDATE workflow_runs SET status='completed',current_stage_id=NULL,
                        terminal_result_json=?,updated_at=? WHERE run_id=?
                    """,
                    (json_text({"result": "completed"}), now, run_id),
                )
                action = "run.complete"
            else:
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET status='running',started_at=COALESCE(started_at,?),updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (now, now, next_stage["run_stage_id"]),
                )
                conn.execute(
                    "UPDATE workflow_runs SET current_stage_id=?,updated_at=? WHERE run_id=?",
                    (next_stage["stage_id"], now, run_id),
                )
                action = "run.stage.advance"
            self.db.audit(
                conn,
                action,
                "workflow_run",
                run_id,
                {"stage_id": stage["stage_id"], "gate_result": gate_result},
            )
        return self.get_run(run_id)

    def fail_current(
        self, run_id: str, gate_result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        now = utc_now()
        gate_result = gate_result or {"passed": False}
        with self.db.transaction() as conn:
            run, stage = self._current(conn, run_id)
            if run["status"] != "active" or stage is None or stage["status"] != "running":
                raise TransitionError("illegal-stage-failure-transition")
            retry_limit = int(stage["retry_limit"])
            retry_count = int(stage["retry_count"])
            if retry_count < retry_limit:
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET retry_count=retry_count+1,gate_result_json=?,updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (json_text(gate_result), now, stage["run_stage_id"]),
                )
                self.db.audit(
                    conn,
                    "run.stage.retry",
                    "workflow_run",
                    run_id,
                    {
                        "stage_id": stage["stage_id"],
                        "retry_count": retry_count + 1,
                        "retry_limit": retry_limit,
                    },
                )
                return self.get_run(run_id)

            resolved = json_value(stage["resolved_bindings_json"], [])
            fallback_bindings = [
                item
                for item in resolved
                if item.get("fallback_skill_id") and not item.get("using_fallback")
            ]
            if fallback_bindings:
                for item in resolved:
                    if item in fallback_bindings:
                        item["primary_skill_id"] = item["skill_id"]
                        item["skill_id"] = item["fallback_skill_id"]
                        item["using_fallback"] = True
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET resolved_bindings_json=?,gate_result_json=?,updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (json_text(resolved), json_text(gate_result), now, stage["run_stage_id"]),
                )
                self.db.audit(
                    conn,
                    "run.stage.fallback-skill",
                    "workflow_run",
                    run_id,
                    {"stage_id": stage["stage_id"]},
                )
                return self.get_run(run_id)

            fallback_stage_id = stage["fallback_stage_id"]
            conn.execute(
                """
                UPDATE workflow_run_stages
                SET status='failed',gate_result_json=?,finished_at=?,updated_at=?
                WHERE run_stage_id=?
                """,
                (json_text(gate_result), now, now, stage["run_stage_id"]),
            )
            if fallback_stage_id:
                fallback = conn.execute(
                    "SELECT * FROM workflow_run_stages WHERE run_id=? AND stage_id=?",
                    (run_id, fallback_stage_id),
                ).fetchone()
                if fallback is None:
                    raise TransitionError("fallback-stage-not-in-run")
                conn.execute(
                    """
                    UPDATE workflow_run_stages
                    SET status='running',started_at=COALESCE(started_at,?),
                        finished_at=NULL,updated_at=?
                    WHERE run_stage_id=?
                    """,
                    (now, now, fallback["run_stage_id"]),
                )
                conn.execute(
                    "UPDATE workflow_runs SET current_stage_id=?,updated_at=? WHERE run_id=?",
                    (fallback_stage_id, now, run_id),
                )
                action = "run.stage.fallback-stage"
            else:
                conn.execute(
                    """
                    UPDATE workflow_runs SET status='failed',current_stage_id=NULL,
                        terminal_result_json=?,updated_at=? WHERE run_id=?
                    """,
                    (
                        json_text({"result": "stage-failed", "stage_id": stage["stage_id"]}),
                        now,
                        run_id,
                    ),
                )
                action = "run.fail"
            self.db.audit(
                conn,
                action,
                "workflow_run",
                run_id,
                {"stage_id": stage["stage_id"], "gate_result": gate_result},
            )
        return self.get_run(run_id)

    def block(self, run_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("blocked-reason-required")
        now = utc_now()
        with self.db.transaction() as conn:
            run, stage = self._current(conn, run_id)
            if run["status"] != "active" or stage is None or stage["status"] != "running":
                raise TransitionError("illegal-block-transition")
            conn.execute(
                """
                UPDATE workflow_run_stages SET status='blocked',blocked_reason=?,updated_at=?
                WHERE run_stage_id=?
                """,
                (reason, now, stage["run_stage_id"]),
            )
            conn.execute(
                "UPDATE workflow_runs SET status='blocked',updated_at=? WHERE run_id=?",
                (now, run_id),
            )
            self.db.audit(
                conn,
                "run.block",
                "workflow_run",
                run_id,
                {"stage_id": stage["stage_id"], "reason": reason},
            )
        return self.get_run(run_id)

    def add_evidence(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        *,
        evidence_key: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.db.transaction() as conn:
            run, stage = self._current(conn, run_id)
            if stage is None:
                raise TransitionError("no-current-stage-for-evidence")
            evidence_id = stable_id("evidence", run_id, stage["run_stage_id"], evidence_key or now)
            conn.execute(
                """
                INSERT INTO workflow_evidence(
                    evidence_id,run_id,run_stage_id,kind,payload_json,created_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    evidence_id,
                    run_id,
                    stage["run_stage_id"],
                    kind,
                    json_text(payload),
                    now,
                ),
            )
            self.db.audit(
                conn,
                "run.evidence.add",
                "workflow_run",
                run_id,
                {"evidence_id": evidence_id, "kind": kind},
            )
        return {"evidence_id": evidence_id, "run_id": run_id, "kind": kind, "payload": payload}

    def resume(self, run_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.db.transaction() as conn:
            run, stage = self._current(conn, run_id)
            if run["status"] != "blocked" or stage is None or stage["status"] != "blocked":
                raise TransitionError("illegal-resume-transition")
            evidence_count = conn.execute(
                "SELECT COUNT(*) AS n FROM workflow_evidence WHERE run_stage_id=?",
                (stage["run_stage_id"],),
            ).fetchone()["n"]
            if int(evidence_count) < 1:
                raise TransitionError("resume-requires-evidence")
            conn.execute(
                """
                UPDATE workflow_run_stages
                SET status='running',blocked_reason=NULL,updated_at=?
                WHERE run_stage_id=?
                """,
                (now, stage["run_stage_id"]),
            )
            conn.execute(
                "UPDATE workflow_runs SET status='active',updated_at=? WHERE run_id=?",
                (now, run_id),
            )
            self.db.audit(
                conn,
                "run.resume",
                "workflow_run",
                run_id,
                {"stage_id": stage["stage_id"], "evidence_count": int(evidence_count)},
            )
        return self.get_run(run_id)
