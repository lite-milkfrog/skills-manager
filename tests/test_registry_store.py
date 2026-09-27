from __future__ import annotations

import hashlib
import json
from pathlib import Path

from conftest import write_skill

from skill_control_plane.core import Registry, SourceRoot
from skill_control_plane.registry_store import RegistryStore
from skill_control_plane.storage import ControlPlaneDB


def test_migration_is_idempotent_and_integrity_clean(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    with ControlPlaneDB(db_path) as db:
        assert db.migrate() == 4
        assert db.migrate() == 4
        rows = db.connection.execute("SELECT * FROM schema_migrations").fetchall()
        assert len(rows) == 4
        integrity = db.integrity()
        assert integrity["integrity_check"] == ["ok"]
        assert integrity["foreign_key_violations"] == []


def test_reconcile_twice_is_semantically_idempotent_and_preserves_archive(
    seeded,
) -> None:
    db = seeded["db"]
    store = seeded["store"]
    snapshot = seeded["snapshot"]

    before = db.connection.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    plan = store.plan_reconcile(snapshot)
    after = db.connection.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    assert plan["dry_run"] is True
    assert before == after

    result = store.reconcile(snapshot)
    assert result["counts"]["skills"]["added"] == 0
    assert result["counts"]["skills"]["updated"] == 0
    assert result["counts"]["skills"]["stale"] == 0
    assert result["counts"]["skills"]["unchanged"] == snapshot["skill_count"]
    assert result["counts"]["variants"]["updated"] == 0
    assert result["counts"]["variants"]["stale"] == 0
    assert result["counts"]["variants"]["unchanged"] == snapshot["variant_count"]

    parity = store.parity(snapshot)
    assert parity["ok"] is True
    assert parity["db_nonselectable_variant_count"] == 1

    duplicate = db.connection.execute(
        """
        SELECT skill_id, COUNT(*) AS n
        FROM skills WHERE active=1
        GROUP BY skill_id HAVING COUNT(*) > 1
        """
    ).fetchall()
    assert duplicate == []


def test_changed_digest_same_path_keeps_history_and_marks_old_variant_stale(
    seeded,
) -> None:
    store = seeded["store"]
    db = seeded["db"]
    path = seeded["paths"]["one"]
    previous = seeded["snapshot"]
    old_variant = next(
        row for row in previous["variants"]["one-skill"] if row["path"] == str(path.absolute())
    )

    path.write_text(
        "---\nname: one-skill\ndescription: Primary one updated.\n---\n\n# one-skill\nchanged\n",
        encoding="utf-8",
    )
    registry = Registry(
        [
            SourceRoot("project_portable", seeded["active"], 1000),
            SourceRoot("shared_agents", seeded["shared"], 900),
        ],
        [seeded["paths"]["archive"]],
    )
    current = registry.build_index()
    result = store.reconcile(current)
    parity = store.parity(current)

    assert result["counts"]["variants"]["stale"] == 1
    assert parity["ok"] is True
    rows = db.connection.execute(
        "SELECT variant_id,active FROM skill_variants WHERE path=? ORDER BY active DESC",
        (str(path.absolute()),),
    ).fetchall()
    assert len(rows) == 2
    assert sum(int(row["active"]) for row in rows) == 1
    assert any(
        row["variant_id"] == old_variant["variant_id"] and int(row["active"]) == 0 for row in rows
    )


def test_legacy_config_is_read_only_compatibility_input(tmp_path: Path) -> None:
    root = tmp_path / ".skills"
    write_skill(root, "one", "one-skill", "One.")
    snapshot = Registry([SourceRoot("project_portable", root, 1000)]).build_index()
    legacy = tmp_path / "config.json"
    legacy.write_text(
        json.dumps({"roots": [str(root)], "files": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    before = (
        hashlib.sha256(legacy.read_bytes()).hexdigest(),
        legacy.stat().st_size,
        legacy.stat().st_mtime_ns,
    )

    with ControlPlaneDB(tmp_path / "state.db") as db:
        result = RegistryStore(db).reconcile(snapshot, legacy_config_path=legacy)

    after = (
        hashlib.sha256(legacy.read_bytes()).hexdigest(),
        legacy.stat().st_size,
        legacy.stat().st_mtime_ns,
    )
    assert before == after
    assert result["compatibility"]["legacy_roots"] == 1
