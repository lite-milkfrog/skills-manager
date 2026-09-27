from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .core import validate_skill_file
from .filesystem_ops import (
    FilesystemSafetyError,
    canonical_path,
    copy_tree,
    move_directory,
    path_key,
    tree_digest,
)
from .storage import ControlPlaneDB, utc_now
from .utils import json_text, json_value, stable_id

OPERATIONS = {
    "adopt_existing",
    "deploy_from_local_source",
    "update_managed",
    "relocate_managed",
    "undeploy_to_quarantine",
}

ACTIVE_STATES = {
    "planned",
    "validated",
    "applying",
    "verifying",
    "recovery_required",
    "rolling_back",
}

LEGAL_TRANSITIONS = {
    "planned": {"validated", "rolling_back"},
    "validated": {"applying", "rolling_back"},
    "applying": {"verifying", "recovery_required", "rolling_back"},
    "verifying": {"committed", "recovery_required", "rolling_back"},
    "recovery_required": {"applying", "rolling_back"},
    "rolling_back": {"rolled_back"},
    "committed": set(),
    "rolled_back": set(),
}

STEP_NAMES = {
    "adopt_existing": ["verify_identity", "prepare_ownership"],
    "deploy_from_local_source": [
        "stage_copy",
        "verify_stage",
        "publish_target",
        "verify_target",
        "prepare_ownership",
    ],
    "update_managed": [
        "stage_copy",
        "verify_stage",
        "quarantine_previous",
        "publish_target",
        "verify_target",
        "prepare_ownership",
    ],
    "relocate_managed": [
        "stage_copy",
        "verify_stage",
        "publish_target",
        "verify_target",
        "quarantine_source",
        "verify_source_retired",
        "prepare_ownership",
    ],
    "undeploy_to_quarantine": [
        "quarantine_source",
        "verify_source_retired",
        "prepare_ownership",
    ],
}


class DeploymentError(RuntimeError):
    pass


class DeploymentPolicyError(DeploymentError):
    pass


class DeploymentConflictError(DeploymentError):
    pass


class DeploymentTransitionError(DeploymentError):
    pass


class InjectedDeploymentFault(BaseException):
    pass


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([path_key(path), path_key(root)]) == path_key(root)
    except ValueError:
        return False


class DeploymentService:
    def __init__(
        self,
        db: ControlPlaneDB,
        *,
        protected_roots: list[Path | str] | tuple[Path | str, ...] = (),
        managed_roots: list[Path | str] | tuple[Path | str, ...] = (),
    ) -> None:
        self.db = db
        self.db.migrate()
        self.protected_roots = tuple(canonical_path(path) for path in protected_roots)
        self.managed_roots = tuple(canonical_path(path) for path in managed_roots)

    def _selected(self, skill_id: str) -> sqlite3.Row:
        row = self.db.connection.execute(
            """
            SELECT s.skill_id,s.name,s.selected_variant_id,
                   v.path,v.sha256,v.selectable,v.active AS variant_active
            FROM skills s
            JOIN skill_variants v ON v.variant_id=s.selected_variant_id
            WHERE s.skill_id=? AND s.active=1
            """,
            (skill_id,),
        ).fetchone()
        if row is None:
            raise DeploymentPolicyError(f"unknown-skill-id:{skill_id}")
        return row

    def _managed_row(self, path: Path | str) -> sqlite3.Row | None:
        return self.db.connection.execute(
            "SELECT * FROM managed_paths WHERE path_key=? AND active=1",
            (path_key(path),),
        ).fetchone()

    def _active_managed_for_skill(self, skill_id: str) -> sqlite3.Row | None:
        return self.db.connection.execute(
            """
            SELECT * FROM managed_paths
            WHERE skill_id=? AND active=1
            ORDER BY path_key
            LIMIT 1
            """,
            (skill_id,),
        ).fetchone()

    def _directory(self, path: Path | str) -> Path:
        candidate = canonical_path(path)
        if candidate.name.casefold() == "skill.md" and candidate.is_file():
            return candidate.parent
        return candidate

    def _is_protected(self, path: Path) -> bool:
        return any(_within(path, root) for root in self.protected_roots)

    def _is_managed_root(self, path: Path) -> bool:
        return any(_within(path, root) for root in self.managed_roots)

    def _classify(self, skill_id: str, directory: Path) -> str:
        if self._is_protected(directory):
            return "protected_wac_project"
        managed = self._managed_row(directory)
        if managed is not None:
            return str(managed["ownership_class"])
        if self._is_managed_root(directory):
            return "control_plane_owned"

        skill_file_key = path_key(directory / "SKILL.md")
        selected_variant_id = str(self._selected(skill_id)["selected_variant_id"])
        rows = self.db.connection.execute(
            """
            SELECT variant_id,path,selectable,active
            FROM skill_variants
            WHERE skill_id=?
            """,
            (skill_id,),
        ).fetchall()
        same_path_rows: list[sqlite3.Row] = []
        for row in rows:
            try:
                same_path = path_key(row["path"]) == skill_file_key
            except FilesystemSafetyError:
                same_path = False
            if same_path:
                same_path_rows.append(row)
        if any(
            str(row["variant_id"]) == selected_variant_id
            and int(row["active"]) == 1
            and int(row["selectable"]) == 1
            for row in same_path_rows
        ):
            return "discovered_unmanaged"
        if any(
            int(row["active"]) == 1 and int(row["selectable"]) == 1
            for row in same_path_rows
        ):
            return "discovered_unmanaged"
        if same_path_rows:
            return "historical_nonselectable"
        return "unknown"

    def _identity(self, skill_id: str, directory: Path) -> dict[str, str]:
        skill_file = directory / "SKILL.md"
        result = validate_skill_file(skill_file)
        if not bool(result.get("ok")):
            raise DeploymentPolicyError(
                f"invalid-skill-body:{skill_file}:{','.join(result.get('errors', []))}"
            )
        if str(result.get("name", "")).casefold() != skill_id.casefold():
            raise DeploymentPolicyError(
                f"skill-id-mismatch:{skill_id}:{result.get('name', '')}"
            )
        return {
            "skill_sha256": str(result["sha256"]),
            "tree_digest": tree_digest(directory),
        }

    def _require_target_policy(self, target: Path) -> None:
        if self._is_protected(target):
            raise DeploymentPolicyError(f"protected-target:{target}")
        if not self._is_managed_root(target):
            raise DeploymentPolicyError(f"target-outside-managed-roots:{target}")

    def _require_mutable_managed(self, skill_id: str, path: Path) -> sqlite3.Row:
        if self._is_protected(path):
            raise DeploymentPolicyError(f"protected-target:{path}")
        row = self._managed_row(path)
        if row is None or str(row["skill_id"]) != skill_id:
            raise DeploymentPolicyError(f"unmanaged-source-mutation-rejected:{path}")
        current = tree_digest(path)
        if current != str(row["content_digest"]):
            raise DeploymentPolicyError(f"managed-path-drift:{path}")
        return row

    def plan(
        self,
        skill_id: str,
        operation: str,
        *,
        source_path: Path | str | None = None,
        target_path: Path | str | None = None,
    ) -> dict[str, Any]:
        if operation not in OPERATIONS:
            raise DeploymentPolicyError(f"unknown-operation:{operation}")
        selected = self._selected(skill_id)
        selected_dir = self._directory(str(selected["path"]))

        source: Path | None = None
        target: Path | None = None
        source_digest: str | None = None
        target_digest: str | None = None
        source_ownership = "unknown"
        preconditions: dict[str, Any] = {
            "selected_variant_id": str(selected["selected_variant_id"]),
        }

        if operation in {"adopt_existing", "deploy_from_local_source", "update_managed"}:
            source = self._directory(source_path or selected_dir)
        elif operation in {"relocate_managed", "undeploy_to_quarantine"}:
            if source_path is None:
                managed = self._active_managed_for_skill(skill_id)
                if managed is None:
                    raise DeploymentPolicyError(f"no-managed-path:{skill_id}")
                source = self._directory(str(managed["path"]))
            else:
                source = self._directory(source_path)

        if source is not None:
            identity = self._identity(skill_id, source)
            source_digest = identity["tree_digest"]
            source_ownership = self._classify(skill_id, source)
            if (
                path_key(source) == path_key(selected_dir)
                and identity["skill_sha256"] != str(selected["sha256"])
            ):
                raise DeploymentPolicyError(
                    f"source-drift-from-selected-variant:{source}"
                )
            preconditions["source_skill_sha256"] = identity["skill_sha256"]
            preconditions["source_tree_digest"] = source_digest
            preconditions["source_ownership"] = source_ownership

        if operation in {"deploy_from_local_source", "update_managed", "relocate_managed"}:
            if target_path is None:
                raise DeploymentPolicyError("target-path-required")
            target = canonical_path(target_path)
            self._require_target_policy(target)

        if operation == "adopt_existing":
            if source_ownership in {
                "protected_wac_project",
                "historical_nonselectable",
                "unknown",
            }:
                raise DeploymentPolicyError(f"adopt-source-rejected:{source_ownership}")
            target_digest = source_digest
        elif operation == "deploy_from_local_source":
            if source_ownership not in {
                "discovered_unmanaged",
                "control_plane_owned",
                "explicitly_adopted_external",
                "protected_wac_project",
            }:
                raise DeploymentPolicyError(f"deploy-source-rejected:{source_ownership}")
            if target is None:
                raise AssertionError("target-required")
            if os.path.lexists(target):
                raise DeploymentPolicyError(f"destination-collision:{target}")
            preconditions["target_absent"] = True
            target_digest = source_digest
        elif operation == "update_managed":
            if target is None:
                raise AssertionError("target-required")
            managed = self._require_mutable_managed(skill_id, target)
            if source_ownership not in {
                "discovered_unmanaged",
                "control_plane_owned",
                "explicitly_adopted_external",
                "protected_wac_project",
            }:
                raise DeploymentPolicyError(f"update-source-rejected:{source_ownership}")
            preconditions["current_target_digest"] = str(managed["content_digest"])
            preconditions["target_ownership"] = str(managed["ownership_class"])
            target_digest = source_digest
        elif operation == "relocate_managed":
            if source is None or target is None:
                raise AssertionError("source-and-target-required")
            managed = self._require_mutable_managed(skill_id, source)
            if os.path.lexists(target):
                raise DeploymentPolicyError(f"destination-collision:{target}")
            preconditions["managed_source_digest"] = str(managed["content_digest"])
            preconditions["source_ownership"] = str(managed["ownership_class"])
            preconditions["target_absent"] = True
            target_digest = source_digest
        elif operation == "undeploy_to_quarantine":
            if source is None:
                raise AssertionError("source-required")
            managed = self._require_mutable_managed(skill_id, source)
            preconditions["managed_source_digest"] = str(managed["content_digest"])
            preconditions["source_ownership"] = str(managed["ownership_class"])

        plan_id = stable_id(
            "dplan",
            skill_id,
            operation,
            str(source or ""),
            str(target or ""),
            source_digest or "",
            target_digest or "",
            json_text(preconditions),
        )
        transaction_id = stable_id("dtxn", plan_id)
        return {
            "dry_run": True,
            "plan_id": plan_id,
            "transaction_id": transaction_id,
            "skill_id": skill_id,
            "operation": operation,
            "source_path": str(source) if source else None,
            "target_path": str(target) if target else None,
            "source_digest": source_digest,
            "target_digest": target_digest,
            "ownership_class": source_ownership,
            "preconditions": preconditions,
            "steps": list(STEP_NAMES[operation]),
        }

    def _fresh_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self.plan(
            str(plan["skill_id"]),
            str(plan["operation"]),
            source_path=plan.get("source_path"),
            target_path=plan.get("target_path"),
        )

    def begin(
        self,
        plan: dict[str, Any],
        *,
        fault_after: str | None = None,
    ) -> dict[str, Any]:
        fresh = self._fresh_plan(plan)
        if fresh["plan_id"] != plan.get("plan_id"):
            raise DeploymentPolicyError("source-or-target-drift-since-plan")
        existing = self.db.connection.execute(
            "SELECT * FROM deployment_transactions WHERE transaction_id=?",
            (str(plan["transaction_id"]),),
        ).fetchone()
        if existing is not None:
            if str(existing["plan_id"]) != str(plan["plan_id"]):
                raise DeploymentConflictError("transaction-id-plan-mismatch")
            return self.get_transaction(str(plan["transaction_id"]))

        now = utc_now()
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO deployment_transactions(
                        transaction_id,plan_id,skill_id,operation,
                        source_path,source_key,target_path,target_key,
                        source_digest,target_digest,ownership_class,
                        preconditions_json,state,rollback_state,evidence_json,
                        error_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'none','{}',NULL,?,?)
                    """,
                    (
                        plan["transaction_id"],
                        plan["plan_id"],
                        plan["skill_id"],
                        plan["operation"],
                        plan.get("source_path"),
                        path_key(plan["source_path"]) if plan.get("source_path") else None,
                        plan.get("target_path"),
                        path_key(plan["target_path"]) if plan.get("target_path") else None,
                        plan.get("source_digest"),
                        plan.get("target_digest"),
                        plan["ownership_class"],
                        json_text(plan["preconditions"]),
                        "planned",
                        now,
                        now,
                    ),
                )
                for ordinal, step_name in enumerate(plan["steps"]):
                    conn.execute(
                        """
                        INSERT INTO deployment_steps(
                            transaction_id,ordinal,step_name,state,evidence_json,updated_at
                        ) VALUES(?,?,?,'pending','{}',?)
                        """,
                        (plan["transaction_id"], ordinal, step_name, now),
                    )
                self.db.audit(
                    conn,
                    "deployment.transaction.planned",
                    "deployment_transaction",
                    str(plan["transaction_id"]),
                    {"plan_id": plan["plan_id"], "operation": plan["operation"]},
                )
        except sqlite3.IntegrityError as exc:
            raise DeploymentConflictError(f"active-transaction-conflict:{exc}") from exc
        self._fault(fault_after, "after_transaction_persisted")
        self._transition(str(plan["transaction_id"]), "validated")
        return self.get_transaction(str(plan["transaction_id"]))

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM deployment_transactions WHERE transaction_id=?",
            (transaction_id,),
        ).fetchone()
        if row is None:
            raise DeploymentError(f"unknown-transaction:{transaction_id}")
        steps = self.db.connection.execute(
            """
            SELECT ordinal,step_name,state,evidence_json,started_at,finished_at,updated_at
            FROM deployment_steps
            WHERE transaction_id=?
            ORDER BY ordinal
            """,
            (transaction_id,),
        ).fetchall()
        result = dict(row)
        result["preconditions"] = json_value(result.pop("preconditions_json"), {})
        result["evidence"] = json_value(result.pop("evidence_json"), {})
        result["error"] = json_value(result.pop("error_json"), None)
        result["steps"] = [
            {
                **dict(step),
                "evidence": json_value(step["evidence_json"], {}),
            }
            for step in steps
        ]
        for step in result["steps"]:
            step.pop("evidence_json", None)
        return result

    def _transition(
        self,
        transaction_id: str,
        new_state: str,
        *,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT state FROM deployment_transactions WHERE transaction_id=?",
                (transaction_id,),
            ).fetchone()
            if row is None:
                raise DeploymentError(f"unknown-transaction:{transaction_id}")
            current = str(row["state"])
            if current == new_state:
                return
            if new_state not in LEGAL_TRANSITIONS.get(current, set()):
                raise DeploymentTransitionError(f"illegal-transition:{current}->{new_state}")
            conn.execute(
                """
                UPDATE deployment_transactions
                SET state=?,error_json=?,updated_at=?
                WHERE transaction_id=?
                """,
                (new_state, json_text(error) if error else None, utc_now(), transaction_id),
            )
            self.db.audit(
                conn,
                "deployment.transaction.transition",
                "deployment_transaction",
                transaction_id,
                {"from": current, "to": new_state, "error": error},
            )

    def _artifact_paths(self, transaction: dict[str, Any]) -> dict[str, Path | None]:
        transaction_id = str(transaction["transaction_id"])
        source = Path(transaction["source_path"]) if transaction.get("source_path") else None
        target = Path(transaction["target_path"]) if transaction.get("target_path") else None

        target_root = (
            target.parent
            / ".trash"
            / "skill-control-plane-transactions"
            / transaction_id
            if target
            else None
        )
        source_root = (
            source.parent
            / ".trash"
            / "skill-control-plane-transactions"
            / transaction_id
            if source
            else None
        )
        return {
            "stage": target_root / "stage" if target_root else None,
            "previous_target": target_root / "previous-target" if target_root else None,
            "rollback_target": target_root / "rollback-target" if target_root else None,
            "source_quarantine": source_root / "source-quarantine" if source_root else None,
        }

    def _mark_step(
        self,
        transaction_id: str,
        step_name: str,
        evidence: dict[str, Any],
    ) -> None:
        now = utc_now()
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT state FROM deployment_steps
                WHERE transaction_id=? AND step_name=?
                """,
                (transaction_id, step_name),
            ).fetchone()
            if row is None:
                raise DeploymentError(f"unknown-step:{transaction_id}:{step_name}")
            if str(row["state"]) == "verified":
                return
            conn.execute(
                """
                UPDATE deployment_steps
                SET state='verified',evidence_json=?,
                    started_at=COALESCE(started_at,?),finished_at=?,updated_at=?
                WHERE transaction_id=? AND step_name=?
                """,
                (
                    json_text(evidence),
                    now,
                    now,
                    now,
                    transaction_id,
                    step_name,
                ),
            )
            self.db.audit(
                conn,
                "deployment.step.verified",
                "deployment_transaction",
                transaction_id,
                {"step": step_name, "evidence": evidence},
            )

    def _fault(self, configured: str | None, point: str) -> None:
        if configured == point:
            raise InjectedDeploymentFault(point)

    def _digest_matches(self, path: Path, expected: str | None) -> bool:
        return path.is_dir() and expected is not None and tree_digest(path) == expected

    def _stage_copy(
        self,
        transaction: dict[str, Any],
        artifacts: dict[str, Path | None],
        fault_after: str | None,
    ) -> dict[str, Any]:
        source = Path(str(transaction["source_path"]))
        target = Path(str(transaction["target_path"]))
        stage = artifacts["stage"]
        if stage is None:
            raise DeploymentError("stage-path-missing")
        expected = str(transaction["target_digest"])
        if stage.is_dir():
            if not self._digest_matches(stage, expected):
                raise DeploymentError("staging-digest-mismatch")
            return {"stage": str(stage), "digest": expected, "recovered": True}
        if (
            path_key(source) != path_key(target)
            and self._digest_matches(target, expected)
        ):
            return {"target": str(target), "digest": expected, "publish_already_visible": True}
        copy_tree(source, stage)
        self._fault(fault_after, "after_stage_created")
        if not self._digest_matches(stage, expected):
            raise DeploymentError("staging-verify-failed")
        return {"stage": str(stage), "digest": expected}

    def _verify_stage(
        self,
        transaction: dict[str, Any],
        artifacts: dict[str, Path | None],
    ) -> dict[str, Any]:
        stage = artifacts["stage"]
        target = Path(str(transaction["target_path"]))
        expected = str(transaction["target_digest"])
        if stage is not None and self._digest_matches(stage, expected):
            return {"stage": str(stage), "digest": expected}
        if self._digest_matches(target, expected):
            return {"target": str(target), "digest": expected, "publish_already_visible": True}
        raise DeploymentError("staging-missing-or-invalid")

    def _publish_target(
        self,
        transaction: dict[str, Any],
        artifacts: dict[str, Path | None],
        fault_after: str | None,
    ) -> dict[str, Any]:
        target = Path(str(transaction["target_path"]))
        stage = artifacts["stage"]
        expected = str(transaction["target_digest"])
        if self._digest_matches(target, expected):
            return {"target": str(target), "digest": expected, "recovered": True}
        if target.exists():
            raise DeploymentError(f"unexpected-target-collision:{target}")
        if stage is None or not self._digest_matches(stage, expected):
            raise DeploymentError("verified-stage-not-available")
        move_directory(stage, target)
        self._fault(fault_after, "after_publish_before_record")
        if not self._digest_matches(target, expected):
            raise DeploymentError("published-target-digest-mismatch")
        return {"target": str(target), "digest": expected}

    def _quarantine_previous(
        self,
        transaction: dict[str, Any],
        artifacts: dict[str, Path | None],
        fault_after: str | None,
    ) -> dict[str, Any]:
        target = Path(str(transaction["target_path"]))
        quarantine = artifacts["previous_target"]
        if quarantine is None:
            raise DeploymentError("previous-target-quarantine-missing")
        expected = str(transaction["preconditions"]["current_target_digest"])
        if self._digest_matches(quarantine, expected):
            return {"quarantine": str(quarantine), "digest": expected, "recovered": True}
        if not self._digest_matches(target, expected):
            raise DeploymentError("target-drift-before-update")
        move_directory(target, quarantine)
        self._fault(fault_after, "after_target_quarantine_before_record")
        if not self._digest_matches(quarantine, expected):
            raise DeploymentError("previous-target-quarantine-verify-failed")
        return {"quarantine": str(quarantine), "digest": expected}

    def _quarantine_source(
        self,
        transaction: dict[str, Any],
        artifacts: dict[str, Path | None],
        fault_after: str | None,
    ) -> dict[str, Any]:
        source = Path(str(transaction["source_path"]))
        quarantine = artifacts["source_quarantine"]
        if quarantine is None:
            raise DeploymentError("source-quarantine-missing")
        expected = str(transaction["source_digest"])
        if self._digest_matches(quarantine, expected) and not source.exists():
            return {"quarantine": str(quarantine), "digest": expected, "recovered": True}
        if not self._digest_matches(source, expected):
            raise DeploymentError("source-drift-before-quarantine")
        move_directory(source, quarantine)
        self._fault(fault_after, "after_source_quarantine_before_record")
        if not self._digest_matches(quarantine, expected):
            raise DeploymentError("source-quarantine-verify-failed")
        return {"quarantine": str(quarantine), "digest": expected}

    def _execute_step(
        self,
        transaction: dict[str, Any],
        step_name: str,
        fault_after: str | None,
    ) -> dict[str, Any]:
        operation = str(transaction["operation"])
        source = Path(str(transaction["source_path"])) if transaction.get("source_path") else None
        target = Path(str(transaction["target_path"])) if transaction.get("target_path") else None
        artifacts = self._artifact_paths(transaction)
        expected = transaction.get("target_digest")

        if step_name == "verify_identity":
            if source is None or tree_digest(source) != transaction["source_digest"]:
                raise DeploymentError("source-drift-during-apply")
            return {"source": str(source), "digest": transaction["source_digest"]}
        if step_name == "stage_copy":
            return self._stage_copy(transaction, artifacts, fault_after)
        if step_name == "verify_stage":
            return self._verify_stage(transaction, artifacts)
        if step_name == "quarantine_previous":
            return self._quarantine_previous(transaction, artifacts, fault_after)
        if step_name == "publish_target":
            return self._publish_target(transaction, artifacts, fault_after)
        if step_name == "verify_target":
            if target is None or not self._digest_matches(target, str(expected)):
                raise DeploymentError("target-verification-failed")
            return {"target": str(target), "digest": expected}
        if step_name == "quarantine_source":
            return self._quarantine_source(transaction, artifacts, fault_after)
        if step_name == "verify_source_retired":
            if source is None:
                raise DeploymentError("source-required")
            quarantine = artifacts["source_quarantine"]
            if source.exists():
                raise DeploymentError("source-still-active-after-quarantine")
            if quarantine is None or not self._digest_matches(
                quarantine, str(transaction["source_digest"])
            ):
                raise DeploymentError("source-quarantine-verification-failed")
            return {"source_absent": str(source), "quarantine": str(quarantine)}
        if step_name == "prepare_ownership":
            return {"operation": operation, "metadata_write_deferred_until_commit": True}
        raise DeploymentError(f"unknown-deployment-step:{step_name}")

    def _final_verify(self, transaction: dict[str, Any]) -> dict[str, Any]:
        operation = str(transaction["operation"])
        source = Path(str(transaction["source_path"])) if transaction.get("source_path") else None
        target = Path(str(transaction["target_path"])) if transaction.get("target_path") else None
        artifacts = self._artifact_paths(transaction)
        if operation == "adopt_existing":
            if source is None or tree_digest(source) != transaction["source_digest"]:
                raise DeploymentError("adopt-final-verify-failed")
            return {"source": str(source), "digest": transaction["source_digest"]}
        if operation in {"deploy_from_local_source", "update_managed", "relocate_managed"}:
            if target is None or not self._digest_matches(
                target, str(transaction["target_digest"])
            ):
                raise DeploymentError("target-final-verify-failed")
        if operation in {"relocate_managed", "undeploy_to_quarantine"}:
            quarantine = artifacts["source_quarantine"]
            if source is None or source.exists():
                raise DeploymentError("source-not-retired")
            if quarantine is None or not self._digest_matches(
                quarantine, str(transaction["source_digest"])
            ):
                raise DeploymentError("source-quarantine-final-verify-failed")
        return {
            "target": str(target) if target else None,
            "target_digest": transaction.get("target_digest"),
            "source_retired": operation in {"relocate_managed", "undeploy_to_quarantine"},
        }

    def _upsert_managed(
        self,
        conn: sqlite3.Connection,
        *,
        path: str,
        skill_id: str,
        ownership_class: str,
        digest: str,
        transaction_id: str,
    ) -> None:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO managed_paths(
                path_key,path,skill_id,ownership_class,content_digest,
                active,origin_transaction_id,created_at,updated_at
            ) VALUES(?,?,?,?,?,1,?,?,?)
            ON CONFLICT(path_key) DO UPDATE SET
                path=excluded.path,
                skill_id=excluded.skill_id,
                ownership_class=excluded.ownership_class,
                content_digest=excluded.content_digest,
                active=1,
                origin_transaction_id=excluded.origin_transaction_id,
                updated_at=excluded.updated_at
            """,
            (
                path_key(path),
                path,
                skill_id,
                ownership_class,
                digest,
                transaction_id,
                now,
                now,
            ),
        )

    def _commit(self, transaction_id: str, evidence: dict[str, Any]) -> None:
        transaction = self.get_transaction(transaction_id)
        if transaction["state"] != "verifying":
            raise DeploymentTransitionError(
                f"commit-requires-verifying:{transaction['state']}"
            )
        operation = str(transaction["operation"])
        source = transaction.get("source_path")
        target = transaction.get("target_path")
        with self.db.transaction() as conn:
            if operation == "adopt_existing":
                self._upsert_managed(
                    conn,
                    path=str(source),
                    skill_id=str(transaction["skill_id"]),
                    ownership_class="explicitly_adopted_external",
                    digest=str(transaction["source_digest"]),
                    transaction_id=transaction_id,
                )
            elif operation == "deploy_from_local_source":
                self._upsert_managed(
                    conn,
                    path=str(target),
                    skill_id=str(transaction["skill_id"]),
                    ownership_class="control_plane_owned",
                    digest=str(transaction["target_digest"]),
                    transaction_id=transaction_id,
                )
            elif operation == "update_managed":
                existing = conn.execute(
                    "SELECT ownership_class FROM managed_paths WHERE path_key=?",
                    (path_key(str(target)),),
                ).fetchone()
                ownership = (
                    str(existing["ownership_class"]) if existing else "control_plane_owned"
                )
                self._upsert_managed(
                    conn,
                    path=str(target),
                    skill_id=str(transaction["skill_id"]),
                    ownership_class=ownership,
                    digest=str(transaction["target_digest"]),
                    transaction_id=transaction_id,
                )
            elif operation == "relocate_managed":
                conn.execute(
                    "UPDATE managed_paths SET active=0,updated_at=? WHERE path_key=?",
                    (utc_now(), path_key(str(source))),
                )
                self._upsert_managed(
                    conn,
                    path=str(target),
                    skill_id=str(transaction["skill_id"]),
                    ownership_class="control_plane_owned",
                    digest=str(transaction["target_digest"]),
                    transaction_id=transaction_id,
                )
            elif operation == "undeploy_to_quarantine":
                conn.execute(
                    "UPDATE managed_paths SET active=0,updated_at=? WHERE path_key=?",
                    (utc_now(), path_key(str(source))),
                )
            else:
                raise DeploymentError(f"unknown-operation:{operation}")
            conn.execute(
                """
                UPDATE deployment_transactions
                SET state='committed',evidence_json=?,error_json=NULL,updated_at=?
                WHERE transaction_id=? AND state='verifying'
                """,
                (json_text(evidence), utc_now(), transaction_id),
            )
            self.db.audit(
                conn,
                "deployment.transaction.committed",
                "deployment_transaction",
                transaction_id,
                evidence,
            )

    def _resume_apply(
        self,
        transaction_id: str,
        *,
        fault_after: str | None = None,
    ) -> dict[str, Any]:
        transaction = self.get_transaction(transaction_id)
        if transaction["state"] == "planned":
            fresh = self.plan(
                str(transaction["skill_id"]),
                str(transaction["operation"]),
                source_path=transaction.get("source_path"),
                target_path=transaction.get("target_path"),
            )
            if fresh["plan_id"] != transaction["plan_id"]:
                raise DeploymentPolicyError("source-or-target-drift-since-persist")
            self._transition(transaction_id, "validated")
            transaction = self.get_transaction(transaction_id)
        if transaction["state"] in {"validated", "recovery_required"}:
            self._transition(transaction_id, "applying")
            transaction = self.get_transaction(transaction_id)
        if transaction["state"] == "applying":
            try:
                for step in transaction["steps"]:
                    if step["state"] == "verified":
                        continue
                    evidence = self._execute_step(
                        self.get_transaction(transaction_id),
                        str(step["step_name"]),
                        fault_after,
                    )
                    self._mark_step(transaction_id, str(step["step_name"]), evidence)
                self._transition(transaction_id, "verifying")
            except Exception as exc:
                current = self.get_transaction(transaction_id)
                if current["state"] in {"applying", "verifying"}:
                    self._transition(
                        transaction_id,
                        "recovery_required",
                        error={"type": type(exc).__name__, "detail": str(exc)},
                    )
                raise
        transaction = self.get_transaction(transaction_id)
        if transaction["state"] == "verifying":
            try:
                evidence = self._final_verify(transaction)
                self._commit(transaction_id, evidence)
            except Exception as exc:
                current = self.get_transaction(transaction_id)
                if current["state"] == "verifying":
                    self._transition(
                        transaction_id,
                        "recovery_required",
                        error={"type": type(exc).__name__, "detail": str(exc)},
                    )
                raise
        return self.get_transaction(transaction_id)

    def apply(
        self,
        plan: dict[str, Any],
        *,
        fault_after: str | None = None,
    ) -> dict[str, Any]:
        transaction = self.begin(plan, fault_after=fault_after)
        if transaction["state"] in {"committed", "rolled_back"}:
            return transaction
        return self._resume_apply(str(transaction["transaction_id"]), fault_after=fault_after)

    def recover(self, transaction_id: str) -> dict[str, Any]:
        transaction = self.get_transaction(transaction_id)
        state = str(transaction["state"])
        if state in {"committed", "rolled_back"}:
            return transaction
        if state == "rolling_back":
            return self._resume_rollback(transaction_id)
        if state not in {
            "planned",
            "validated",
            "applying",
            "verifying",
            "recovery_required",
        }:
            raise DeploymentTransitionError(f"illegal-recovery-state:{state}")
        return self._resume_apply(transaction_id)

    def _restore_from_quarantine(
        self,
        source: Path,
        quarantine: Path,
        expected: str,
    ) -> None:
        if self._digest_matches(source, expected):
            return
        if source.exists():
            raise DeploymentError(f"rollback-destination-drift:{source}")
        if not self._digest_matches(quarantine, expected):
            raise DeploymentError(f"rollback-material-missing:{quarantine}")
        move_directory(quarantine, source)

    def _resume_rollback(
        self,
        transaction_id: str,
        *,
        fault_after: str | None = None,
    ) -> dict[str, Any]:
        transaction = self.get_transaction(transaction_id)
        if transaction["state"] != "rolling_back":
            raise DeploymentTransitionError(
                f"rollback-resume-requires-rolling_back:{transaction['state']}"
            )
        operation = str(transaction["operation"])
        source = Path(str(transaction["source_path"])) if transaction.get("source_path") else None
        target = Path(str(transaction["target_path"])) if transaction.get("target_path") else None
        artifacts = self._artifact_paths(transaction)

        if operation == "deploy_from_local_source" and target is not None:
            rollback_target = artifacts["rollback_target"]
            if self._digest_matches(target, str(transaction["target_digest"])):
                if rollback_target is None:
                    raise DeploymentError("rollback-target-path-missing")
                if rollback_target.exists():
                    raise DeploymentError("rollback-target-quarantine-collision")
                move_directory(target, rollback_target)
        elif operation == "update_managed" and target is not None:
            rollback_target = artifacts["rollback_target"]
            previous = artifacts["previous_target"]
            old_digest = str(transaction["preconditions"]["current_target_digest"])
            if self._digest_matches(target, str(transaction["target_digest"])):
                if rollback_target is None:
                    raise DeploymentError("rollback-target-path-missing")
                if not rollback_target.exists():
                    move_directory(target, rollback_target)
            if previous is None:
                raise DeploymentError("previous-target-quarantine-missing")
            self._restore_from_quarantine(target, previous, old_digest)
        elif operation == "relocate_managed":
            if target is None or source is None:
                raise DeploymentError("relocate-paths-missing")
            rollback_target = artifacts["rollback_target"]
            if self._digest_matches(target, str(transaction["target_digest"])):
                if rollback_target is None:
                    raise DeploymentError("rollback-target-path-missing")
                if not rollback_target.exists():
                    move_directory(target, rollback_target)
            source_quarantine = artifacts["source_quarantine"]
            if source_quarantine is None:
                raise DeploymentError("source-quarantine-missing")
            self._restore_from_quarantine(
                source,
                source_quarantine,
                str(transaction["source_digest"]),
            )
        elif operation == "undeploy_to_quarantine":
            if source is None:
                raise DeploymentError("source-path-missing")
            source_quarantine = artifacts["source_quarantine"]
            if source_quarantine is None:
                raise DeploymentError("source-quarantine-missing")
            self._restore_from_quarantine(
                source,
                source_quarantine,
                str(transaction["source_digest"]),
            )
        elif operation == "adopt_existing":
            pass
        else:
            raise DeploymentError(f"unknown-operation:{operation}")

        self._fault(fault_after, "after_rollback_restore_before_record")
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE deployment_transactions
                SET state='rolled_back',rollback_state='restored',error_json=NULL,updated_at=?
                WHERE transaction_id=? AND state='rolling_back'
                """,
                (utc_now(), transaction_id),
            )
            self.db.audit(
                conn,
                "deployment.transaction.rolled_back",
                "deployment_transaction",
                transaction_id,
                {"operation": operation},
            )
        return self.get_transaction(transaction_id)

    def rollback(
        self,
        transaction_id: str,
        *,
        fault_after: str | None = None,
    ) -> dict[str, Any]:
        transaction = self.get_transaction(transaction_id)
        state = str(transaction["state"])
        if state == "rolled_back":
            return transaction
        if state == "committed":
            raise DeploymentTransitionError("committed-transaction-is-terminal")
        if state != "rolling_back":
            if state not in {
                "planned",
                "validated",
                "applying",
                "verifying",
                "recovery_required",
            }:
                raise DeploymentTransitionError(f"illegal-rollback-state:{state}")
            self._transition(transaction_id, "rolling_back")
        return self._resume_rollback(transaction_id, fault_after=fault_after)
