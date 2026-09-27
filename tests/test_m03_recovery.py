from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_skill

from skill_control_plane.deployment import (
    DeploymentService,
    DeploymentTransitionError,
    InjectedDeploymentFault,
)
from skill_control_plane.filesystem_ops import tree_digest
from skill_control_plane.storage import ControlPlaneDB


def open_service(
    db_path: Path,
    *,
    managed: Path,
    protected: Path,
) -> tuple[ControlPlaneDB, DeploymentService]:
    db = ControlPlaneDB(db_path)
    service = DeploymentService(
        db,
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    return db, service


def test_reopen_from_persisted_planned_and_validated(seeded, tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    source = seeded["paths"]["one"].parent
    plan = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=source,
        target_path=managed / "planned-one",
    )
    with pytest.raises(
        InjectedDeploymentFault, match="after_transaction_persisted"
    ):
        service.apply(plan, fault_after="after_transaction_persisted")
    assert service.get_transaction(plan["transaction_id"])["state"] == "planned"

    db_path = seeded["db"].path
    seeded["db"].close()
    reopened_db, reopened = open_service(
        db_path,
        managed=managed,
        protected=protected,
    )
    recovered = reopened.recover(plan["transaction_id"])
    assert recovered["state"] == "committed"
    reopened_db.close()

    db2 = ControlPlaneDB(tmp_path / "validated.db")
    from skill_control_plane.registry_store import RegistryStore

    RegistryStore(db2).reconcile(seeded["snapshot"])
    validated_service = DeploymentService(
        db2,
        protected_roots=(protected,),
        managed_roots=(managed / "validated-root",),
    )
    validated_plan = validated_service.plan(
        "two-skill",
        "deploy_from_local_source",
        source_path=seeded["paths"]["two"].parent,
        target_path=managed / "validated-root" / "two",
    )
    started = validated_service.begin(validated_plan)
    assert started["state"] == "validated"
    db2_path = db2.path
    db2.close()
    db2_reopen, service2 = open_service(
        db2_path,
        managed=managed / "validated-root",
        protected=protected,
    )
    assert service2.recover(validated_plan["transaction_id"])["state"] == "committed"
    db2_reopen.close()


def test_partial_stage_and_publish_recover_after_reopen(seeded, tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    db_path = seeded["db"].path

    stage_plan = service.plan(
        "one-skill",
        "deploy_from_local_source",
        source_path=seeded["paths"]["one"].parent,
        target_path=managed / "stage-recovery",
    )
    with pytest.raises(InjectedDeploymentFault, match="after_stage_created"):
        service.apply(stage_plan, fault_after="after_stage_created")
    assert service.get_transaction(stage_plan["transaction_id"])["state"] == "applying"
    seeded["db"].close()

    db1, reopened = open_service(db_path, managed=managed, protected=protected)
    stage_recovered = reopened.recover(stage_plan["transaction_id"])
    assert stage_recovered["state"] == "committed"
    assert tree_digest(managed / "stage-recovery") == stage_plan["target_digest"]

    publish_plan = reopened.plan(
        "two-skill",
        "deploy_from_local_source",
        source_path=seeded["paths"]["two"].parent,
        target_path=managed / "publish-recovery",
    )
    with pytest.raises(InjectedDeploymentFault, match="after_publish_before_record"):
        reopened.apply(publish_plan, fault_after="after_publish_before_record")
    assert (managed / "publish-recovery").is_dir()
    assert reopened.get_transaction(publish_plan["transaction_id"])["state"] == "applying"
    db1.close()

    db2, reopened2 = open_service(db_path, managed=managed, protected=protected)
    publish_recovered = reopened2.recover(publish_plan["transaction_id"])
    assert publish_recovered["state"] == "committed"
    assert tree_digest(managed / "publish-recovery") == publish_plan["target_digest"]
    db2.close()


def test_mid_relocate_and_undeploy_recover_after_reopen(seeded, tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    installed = managed / "three"
    service.apply(
        service.plan(
            "three-skill",
            "deploy_from_local_source",
            source_path=seeded["paths"]["three"].parent,
            target_path=installed,
        )
    )
    original_digest = tree_digest(installed)
    relocated = managed / "moved" / "three"
    relocate_plan = service.plan(
        "three-skill",
        "relocate_managed",
        source_path=installed,
        target_path=relocated,
    )
    with pytest.raises(
        InjectedDeploymentFault, match="after_source_quarantine_before_record"
    ):
        service.apply(
            relocate_plan,
            fault_after="after_source_quarantine_before_record",
        )
    assert relocated.is_dir()
    assert not installed.exists()

    db_path = seeded["db"].path
    seeded["db"].close()
    db1, reopened = open_service(db_path, managed=managed, protected=protected)
    relocated_tx = reopened.recover(relocate_plan["transaction_id"])
    assert relocated_tx["state"] == "committed"
    assert tree_digest(relocated) == original_digest

    undeploy_plan = reopened.plan(
        "three-skill",
        "undeploy_to_quarantine",
        source_path=relocated,
    )
    with pytest.raises(
        InjectedDeploymentFault, match="after_source_quarantine_before_record"
    ):
        reopened.apply(
            undeploy_plan,
            fault_after="after_source_quarantine_before_record",
        )
    assert not relocated.exists()
    db1.close()

    db2, reopened2 = open_service(db_path, managed=managed, protected=protected)
    undeployed = reopened2.recover(undeploy_plan["transaction_id"])
    assert undeployed["state"] == "committed"
    assert not relocated.exists()
    db2.close()


def test_partial_rollback_reopen_idempotence_and_terminal_guards(
    seeded, tmp_path: Path
) -> None:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )
    target = managed / "one"
    committed = service.apply(
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=seeded["paths"]["one"].parent,
            target_path=target,
        )
    )
    old_digest = tree_digest(target)
    with pytest.raises(DeploymentTransitionError, match="committed-transaction-is-terminal"):
        service.rollback(committed["transaction_id"])

    replacement = write_skill(
        managed,
        "replacement",
        "one-skill",
        "Replacement for partial rollback recovery.",
    ).parent
    update_plan = service.plan(
        "one-skill",
        "update_managed",
        source_path=replacement,
        target_path=target,
    )
    with pytest.raises(InjectedDeploymentFault, match="after_publish_before_record"):
        service.apply(update_plan, fault_after="after_publish_before_record")
    with pytest.raises(
        InjectedDeploymentFault, match="after_rollback_restore_before_record"
    ):
        service.rollback(
            update_plan["transaction_id"],
            fault_after="after_rollback_restore_before_record",
        )
    assert service.get_transaction(update_plan["transaction_id"])["state"] == (
        "rolling_back"
    )
    assert tree_digest(target) == old_digest

    db_path = seeded["db"].path
    seeded["db"].close()
    db2, reopened = open_service(db_path, managed=managed, protected=protected)
    rolled_back = reopened.recover(update_plan["transaction_id"])
    assert rolled_back["state"] == "rolled_back"
    again = reopened.rollback(update_plan["transaction_id"])
    assert again["state"] == "rolled_back"
    assert tree_digest(target) == old_digest

    with pytest.raises(DeploymentTransitionError, match="illegal-transition"):
        reopened._transition(committed["transaction_id"], "applying")
    db2.close()
