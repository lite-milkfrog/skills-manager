from __future__ import annotations

from pathlib import Path

from skill_control_plane.core import Registry, SourceRoot
from skill_control_plane.deployment import DeploymentService
from skill_control_plane.filesystem_ops import tree_digest


def test_controlled_relocate_rediscovery_and_sqlite_parity(seeded, tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    protected = tmp_path / "protected"
    protected.mkdir()
    service = DeploymentService(
        seeded["db"],
        protected_roots=(protected,),
        managed_roots=(managed,),
    )

    installed = managed / "canary-a"
    service.apply(
        service.plan(
            "one-skill",
            "deploy_from_local_source",
            source_path=seeded["paths"]["one"].parent,
            target_path=installed,
        )
    )
    digest = tree_digest(installed)

    relocated = managed / "canary-b"
    transaction = service.apply(
        service.plan(
            "one-skill",
            "relocate_managed",
            source_path=installed,
            target_path=relocated,
        )
    )
    assert transaction["state"] == "committed"
    assert not installed.exists()
    assert tree_digest(relocated) == digest

    # Reuse the M01 resolver. The transaction-owned .trash copy must be retained
    # only as historical/non-selectable evidence, never as another winner.
    registry = Registry(
        [
            SourceRoot("project_portable", managed, 1100),
            SourceRoot("project_portable", seeded["active"], 1000),
            SourceRoot("shared_agents", seeded["shared"], 900),
        ]
    )
    snapshot = registry.build_index()
    selected = next(row for row in snapshot["skills"] if row["skill_id"] == "one-skill")
    variants = snapshot["variants"]["one-skill"]

    assert Path(selected["path"]).parent == relocated.absolute()
    assert selected["authority_tier"] == 1100
    assert selected["selectable"] is True
    assert (
        sum(
            1
            for row in variants
            if row["selectable"] and row["authority_tier"] == 1100
        )
        == 1
    )
    quarantine = [row for row in variants if ".trash" in Path(row["path"]).parts]
    assert quarantine
    assert all(row["selectable"] is False for row in quarantine)
    assert all(row["source_class"] == "historical_archive" for row in quarantine)

    result = seeded["store"].reconcile(snapshot)
    parity = seeded["store"].parity(snapshot)
    assert result["counts"]["variants"]["added"] >= 0
    assert parity["ok"] is True
    assert parity["selected_mismatches"] == []
    assert parity["variant_mismatches"] == []
