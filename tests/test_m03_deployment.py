from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import write_skill

from skill_control_plane.deployment import (
    DeploymentConflictError,
    DeploymentPolicyError,
    DeploymentService,
    InjectedDeploymentFault,
)
from skill_control_plane.filesystem_ops import FilesystemSafetyError, tree_digest
from skill_control_plane.storage import ControlPlaneDB


def service_for(seeded, tmp_path: Path) -> tuple[DeploymentService, Path, Path]:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected-wac"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    return service, managed, protected


def test_schema_v3_fresh_upgrade_idempotence_and_failure_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    fresh = ControlPlaneDB(tmp_path / "fresh.db")
    assert fresh.migrate() == 4
    assert fresh.migrate() == 4
    assert fresh.integrity() == {
        "integrity_check": ["ok"],
        "foreign_key_violations": [],
        "schema_version": 4,
    }
    fresh.close()

    v2 = ControlPlaneDB(tmp_path / "v2.db")
    with v2.transaction() as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations(
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        v2._migration_001(conn)
        v2._migration_002(conn)
        conn.execute("INSERT INTO schema_migrations VALUES(1,'management-workflow-run-core','now')")
        conn.execute("INSERT INTO schema_migrations VALUES(2,'variant-path-history','now')")
        conn.execute(
            """
            INSERT INTO skills(
                skill_id,name,description,selected_variant_id,category_router,
                active,first_seen_at,last_seen_at,updated_at
            ) VALUES('keep-me','keep-me','Keep me',NULL,0,1,'now','now','now')
            """
        )
    before = {row["skill_id"] for row in v2.connection.execute("SELECT skill_id FROM skills")}
    assert v2.migrate() == 4
    after = {row["skill_id"] for row in v2.connection.execute("SELECT skill_id FROM skills")}
    assert before == after == {"keep-me"}
    assert v2.integrity()["foreign_key_violations"] == []
    v2.close()

    failing = ControlPlaneDB(tmp_path / "failing-v3.db")
    with failing.transaction() as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations(
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        failing._migration_001(conn)
        failing._migration_002(conn)
        conn.execute("INSERT INTO schema_migrations VALUES(1,'management-workflow-run-core','now')")
        conn.execute("INSERT INTO schema_migrations VALUES(2,'variant-path-history','now')")

    original = failing._migration_003

    def fail_v3(conn) -> None:
        original(conn)
        raise RuntimeError("forced-v3-failure")

    monkeypatch.setattr(failing, "_migration_003", fail_v3)
    with pytest.raises(RuntimeError, match="forced-v3-failure"):
        failing.migrate()
    assert failing.schema_version() == 2
    table = failing.connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='deployment_transactions'
        """
    ).fetchone()
    assert table is None
    failing.close()


def test_dry_run_is_deterministic_read_only_and_policy_guarded(
    seeded, tmp_path: Path, monkeypatch
) -> None:
    service, managed, protected = service_for(seeded, tmp_path)
    source = seeded["paths"]["one"].parent
    target = managed / "one"

    before_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    before_tx = (
        seeded["db"]
        .connection.execute("SELECT COUNT(*) AS n FROM deployment_transactions")
        .fetchone()["n"]
    )
    first = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=source,
        target_path=target,
    )
    second = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=source,
        target_path=target,
    )
    after_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    after_tx = (
        seeded["db"]
        .connection.execute("SELECT COUNT(*) AS n FROM deployment_transactions")
        .fetchone()["n"]
    )
    assert first == second
    assert first["dry_run"] is True
    assert before_paths == after_paths
    assert before_tx == after_tx
    assert not target.exists()

    with pytest.raises(DeploymentPolicyError, match="unknown-skill-id"):
        service.plan(
            "missing-skill",
            "deploy_from_local_source",
            source_path=source,
            target_path=managed / "missing",
        )

    with pytest.raises(DeploymentPolicyError, match="deploy-source-rejected"):
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=seeded["paths"]["archive"].parent,
            target_path=managed / "archive-copy",
        )

    with pytest.raises(DeploymentPolicyError, match="protected-target"):
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=source,
            target_path=protected / "one",
        )

    collision = managed / "collision"
    write_skill(managed, "collision", "one-skill", "Collision.")
    with pytest.raises(DeploymentPolicyError, match="destination-collision"):
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=source,
            target_path=collision,
        )

    with pytest.raises(DeploymentPolicyError, match="unmanaged-source-mutation-rejected"):
        service.plan(
            "one-skill",
            "relocate_managed",
            source_path=source,
            target_path=managed / "relocated-unmanaged",
        )

    reparse_source = write_skill(
        managed,
        "reparse-source",
        "one-skill",
        "Synthetic reparse rejection.",
    ).parent
    (reparse_source / "blocked").write_text("blocked", encoding="utf-8")
    import skill_control_plane.filesystem_ops as filesystem_ops

    original = filesystem_ops._entry_is_reparse
    monkeypatch.setattr(
        filesystem_ops,
        "_entry_is_reparse",
        lambda entry: entry.name == "blocked" or original(entry),
    )
    with pytest.raises(FilesystemSafetyError, match="reparse-point-blocked"):
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=reparse_source,
            target_path=managed / "blocked-target",
        )


def test_source_drift_and_sqlite_concurrency_conflicts(seeded, tmp_path: Path) -> None:
    service, managed, _protected = service_for(seeded, tmp_path)
    source = seeded["paths"]["one"].parent
    drift_plan = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=source,
        target_path=managed / "drift-target",
    )
    seeded["paths"]["one"].write_text(
        "---\nname: one-skill\ndescription: Drifted.\n---\n\n# changed\n",
        encoding="utf-8",
    )
    with pytest.raises(DeploymentPolicyError, match="source-drift"):
        service.begin(drift_plan)

    source_two = seeded["paths"]["two"].parent
    plan_a = service.plan(
        "two-skill",
        "deploy_from_local_source",
        source_path=source_two,
        target_path=managed / "two-a",
    )
    plan_b = service.plan(
        "two-skill",
        "deploy_from_local_source",
        source_path=source_two,
        target_path=managed / "two-b",
    )
    service.begin(plan_a)
    with pytest.raises(DeploymentConflictError, match="active-transaction-conflict"):
        service.begin(plan_b)
    assert service.rollback(plan_a["transaction_id"])["state"] == "rolled_back"


def test_current_selected_same_path_wins_over_inactive_digest_history(
    seeded, tmp_path: Path
) -> None:
    path = seeded["paths"]["one"]
    path.write_text(
        "---\nname: one-skill\ndescription: New current digest.\n---\n\n# changed\n",
        encoding="utf-8",
    )
    current = seeded["registry"].build_index()
    seeded["store"].reconcile(current)
    service, managed, _protected = service_for(seeded, tmp_path)
    plan = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=path.parent,
        target_path=managed / "same-path-history",
    )
    assert plan["ownership_class"] == "discovered_unmanaged"


def test_controlled_physical_deploy_adopt_update_rollback_and_audit(seeded, tmp_path: Path) -> None:
    service, managed, _protected = service_for(seeded, tmp_path)

    source = seeded["paths"]["one"].parent
    target = managed / "one"
    deploy = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=source,
        target_path=target,
    )
    deployed = service.apply(deploy)
    assert deployed["state"] == "committed"
    old_digest = tree_digest(target)
    assert old_digest == tree_digest(source)
    assert all(step["state"] == "verified" for step in deployed["steps"])

    adopt_source = seeded["paths"]["two"].parent
    before_bytes = seeded["paths"]["two"].read_bytes()
    before_mtime = seeded["paths"]["two"].stat().st_mtime_ns
    adopt = service.plan(
        "two-skill",
        "adopt_existing",
        source_path=adopt_source,
    )
    adopted = service.apply(adopt)
    assert adopted["state"] == "committed"
    assert seeded["paths"]["two"].read_bytes() == before_bytes
    assert seeded["paths"]["two"].stat().st_mtime_ns == before_mtime
    adopted_row = (
        seeded["db"]
        .connection.execute(
            "SELECT * FROM managed_paths WHERE path_key=?",
            (os.path.normcase(str(adopt_source.resolve())),),
        )
        .fetchone()
    )
    assert adopted_row["ownership_class"] == "explicitly_adopted_external"

    replacement = write_skill(
        managed,
        "replacement-one",
        "one-skill",
        "Replacement body for rollback.",
    ).parent
    update = service.plan(
        "one-skill",
        "update_managed",
        source_path=replacement,
        target_path=target,
    )
    with pytest.raises(InjectedDeploymentFault, match="after_publish_before_record"):
        service.apply(update, fault_after="after_publish_before_record")
    interrupted = service.get_transaction(update["transaction_id"])
    assert interrupted["state"] == "applying"
    assert tree_digest(target) == update["target_digest"]

    rolled_back = service.rollback(update["transaction_id"])
    assert rolled_back["state"] == "rolled_back"
    assert tree_digest(target) == old_digest

    audits = (
        seeded["db"]
        .connection.execute(
            """
        SELECT COUNT(*) AS n FROM audit_log
        WHERE entity_type='deployment_transaction'
        """
        )
        .fetchone()["n"]
    )
    assert audits > 0


def test_relocate_digest_preservation_and_undeploy_restore(seeded, tmp_path: Path) -> None:
    service, managed, _protected = service_for(seeded, tmp_path)
    source = seeded["paths"]["three"].parent
    installed = managed / "three"
    service.apply(
        service.plan(
            "three-skill",
            "deploy_from_local_source",
            source_path=source,
            target_path=installed,
        )
    )
    installed_digest = tree_digest(installed)

    relocated_path = managed / "relocated" / "three"
    relocate = service.plan(
        "three-skill",
        "relocate_managed",
        source_path=installed,
        target_path=relocated_path,
    )
    relocated = service.apply(relocate)
    assert relocated["state"] == "committed"
    assert not installed.exists()
    assert tree_digest(relocated_path) == installed_digest

    undeploy = service.plan(
        "three-skill",
        "undeploy_to_quarantine",
        source_path=relocated_path,
    )
    with pytest.raises(InjectedDeploymentFault, match="after_source_quarantine_before_record"):
        service.apply(undeploy, fault_after="after_source_quarantine_before_record")
    assert not relocated_path.exists()
    restored = service.rollback(undeploy["transaction_id"])
    assert restored["state"] == "rolled_back"
    assert tree_digest(relocated_path) == installed_digest


def test_managed_self_update_stages_before_quarantine(seeded, tmp_path: Path) -> None:
    service, managed, _protected = service_for(seeded, tmp_path)
    target = managed / "self-update"
    service.apply(
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=seeded["paths"]["one"].parent,
            target_path=target,
        )
    )
    before = tree_digest(target)
    update = service.plan(
        "one-skill",
        "update_managed",
        source_path=target,
        target_path=target,
    )
    with pytest.raises(InjectedDeploymentFault, match="after_publish_before_record"):
        service.apply(update, fault_after="after_publish_before_record")
    rolled_back = service.rollback(update["transaction_id"])
    assert rolled_back["state"] == "rolled_back"
    assert tree_digest(target) == before
