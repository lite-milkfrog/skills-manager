from __future__ import annotations

import copy
from pathlib import Path

import pytest

from skill_control_plane.management import ManagementService, ValidationError
from skill_control_plane.registry_store import RegistryStore
from skill_control_plane.run_state import RunService, TransitionError
from skill_control_plane.server import tools_schema
from skill_control_plane.storage import ControlPlaneDB
from skill_control_plane.workflow import WorkflowService


def test_discovery_mcp_tool_names_are_preserved() -> None:
    assert [tool["name"] for tool in tools_schema()] == [
        "skills_status",
        "skills_list",
        "skills_search",
        "skills_get",
        "skills_resources",
        "skills_resolve",
        "skills_validate",
        "skills_evaluate",
    ]


def snapshot_for(tmp_path: Path) -> tuple[dict, Path]:
    active_root = tmp_path / "active"
    archive_root = tmp_path / "archive"
    alpha_path = active_root / "alpha" / "SKILL.md"
    beta_path = active_root / "beta" / "SKILL.md"
    archive_path = archive_root / "alpha" / "SKILL.md"
    alpha_path.parent.mkdir(parents=True)
    beta_path.parent.mkdir(parents=True)
    archive_path.parent.mkdir(parents=True)
    alpha_path.write_text("---\nname: alpha\n---\nkeep-alpha", encoding="utf-8")
    beta_path.write_text("---\nname: beta\n---\nkeep-beta", encoding="utf-8")
    archive_path.write_text("---\nname: alpha\n---\nold-alpha", encoding="utf-8")

    snapshot = {
        "skills": [
            {
                "skill_id": "alpha",
                "name": "alpha",
                "description": "Alpha",
                "variant_id": "variant-alpha-active",
                "sha256": "alpha-active",
                "category_router": False,
            },
            {
                "skill_id": "beta",
                "name": "beta",
                "description": "Beta",
                "variant_id": "variant-beta-active",
                "sha256": "beta-active",
                "category_router": False,
            },
        ],
        "variants": {
            "alpha": [
                {
                    "variant_id": "variant-alpha-active",
                    "skill_id": "alpha",
                    "source_class": "project_portable",
                    "root": str(active_root),
                    "path": str(alpha_path),
                    "sha256": "alpha-active",
                    "size": alpha_path.stat().st_size,
                    "authority_tier": 1000,
                    "selectable": True,
                    "priority": 1000,
                    "category_router": False,
                },
                {
                    "variant_id": "variant-alpha-archive",
                    "skill_id": "alpha",
                    "source_class": "historical_archive",
                    "root": str(archive_root),
                    "path": str(archive_path),
                    "sha256": "alpha-archive",
                    "size": archive_path.stat().st_size,
                    "authority_tier": 0,
                    "selectable": False,
                    "priority": 0,
                    "category_router": False,
                },
            ],
            "beta": [
                {
                    "variant_id": "variant-beta-active",
                    "skill_id": "beta",
                    "source_class": "project_portable",
                    "root": str(active_root),
                    "path": str(beta_path),
                    "sha256": "beta-active",
                    "size": beta_path.stat().st_size,
                    "authority_tier": 1000,
                    "selectable": True,
                    "priority": 1000,
                    "category_router": False,
                }
            ],
        },
    }
    return snapshot, alpha_path


def open_seeded(tmp_path: Path) -> tuple[ControlPlaneDB, dict, Path]:
    snapshot, alpha_path = snapshot_for(tmp_path)
    db = ControlPlaneDB(tmp_path / "control-plane.db")
    RegistryStore(db).reconcile(snapshot)
    return db, snapshot, alpha_path


def test_migration_is_transactional_and_idempotent(tmp_path: Path, monkeypatch) -> None:
    failing_path = tmp_path / "failing.db"
    db = ControlPlaneDB(failing_path)
    original = db._migration_001

    def fail_after_schema(conn) -> None:
        original(conn)
        raise RuntimeError("force-migration-rollback")

    monkeypatch.setattr(db, "_migration_001", fail_after_schema)
    with pytest.raises(RuntimeError, match="force-migration-rollback"):
        db.migrate()

    tables = {
        row["name"]
        for row in db.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "skills" not in tables
    assert "schema_migrations" not in tables
    db.close()

    good = ControlPlaneDB(tmp_path / "good.db")
    assert good.migrate() == 4
    assert good.migrate() == 4
    assert good.integrity() == {
        "integrity_check": ["ok"],
        "foreign_key_violations": [],
        "schema_version": 4,
    }
    assert (
        good.connection.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"] == 4
    )
    good.close()


def test_v1_variant_path_unique_migrates_to_v2_history_model(tmp_path: Path) -> None:
    db = ControlPlaneDB(tmp_path / "v1.db")
    now = "2026-09-22T00:00:00+00:00"
    with db.transaction() as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations(
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE sources(
                source_id INTEGER PRIMARY KEY,
                source_key TEXT NOT NULL UNIQUE,
                source_class TEXT NOT NULL,
                path TEXT NOT NULL,
                authority_tier INTEGER NOT NULL,
                selectable INTEGER NOT NULL,
                active INTEGER NOT NULL,
                last_seen_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE skills(
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                selected_variant_id TEXT,
                category_router INTEGER NOT NULL,
                active INTEGER NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE skill_variants(
                variant_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
                path TEXT NOT NULL UNIQUE,
                root TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                authority_tier INTEGER NOT NULL,
                selectable INTEGER NOT NULL,
                priority INTEGER NOT NULL,
                category_router INTEGER NOT NULL,
                active INTEGER NOT NULL,
                last_seen_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations VALUES(1,'management-workflow-run-core',?)",
            (now,),
        )
        conn.execute(
            """
            INSERT INTO sources
            VALUES(1,'source','project_portable','C:/skills',1000,1,1,NULL,?,?)
            """,
            (now, now),
        )
        conn.execute(
            "INSERT INTO skills VALUES('alpha','alpha','Alpha','v1',0,1,?,?,?)",
            (now, now, now),
        )
        conn.execute(
            """
            INSERT INTO skill_variants
            VALUES('v1','alpha',1,'C:/skills/alpha/SKILL.md','C:/skills','sha1',
                   1,1000,1,1000,0,1,NULL,?,?)
            """,
            (now, now),
        )

    assert db.migrate() == 4
    schema = db.connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='skill_variants'"
    ).fetchone()["sql"]
    assert "path TEXT NOT NULL UNIQUE" not in schema
    db.connection.execute(
        """
        INSERT INTO skill_variants
        VALUES('v2','alpha',1,'C:/skills/alpha/SKILL.md','C:/skills','sha2',
               2,1000,1,1000,0,1,NULL,?,?)
        """,
        (now, now),
    )
    db.connection.commit()
    assert (
        db.connection.execute(
            "SELECT COUNT(*) AS n FROM skill_variants WHERE path='C:/skills/alpha/SKILL.md'"
        ).fetchone()["n"]
        == 2
    )
    db.close()


def test_registry_reconcile_idempotence_parity_and_stale(tmp_path: Path) -> None:
    snapshot, _ = snapshot_for(tmp_path)
    db = ControlPlaneDB(tmp_path / "registry.db")
    store = RegistryStore(db)

    first = store.reconcile(snapshot)
    second = store.reconcile(snapshot)
    audit_before = db.connection.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    plan = store.plan_reconcile(snapshot)
    assert plan["dry_run"] is True
    assert plan["diff"]["ok"] is True
    assert (
        db.connection.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"] == audit_before
    )
    assert first["counts"]["skills"]["added"] == 2
    assert second["counts"]["skills"] == {
        "added": 0,
        "updated": 0,
        "unchanged": 2,
        "stale": 0,
    }
    assert second["counts"]["variants"] == {
        "added": 0,
        "updated": 0,
        "unchanged": 3,
        "stale": 0,
    }
    parity = store.parity(snapshot)
    assert parity["ok"] is True
    assert parity["db_nonselectable_variant_count"] == 1

    selected = db.connection.execute(
        """
        SELECT v.path, v.authority_tier, v.selectable
        FROM skills s
        JOIN skill_variants v ON v.variant_id=s.selected_variant_id
        WHERE s.skill_id='alpha'
        """
    ).fetchone()
    assert selected["authority_tier"] == 1000
    assert selected["selectable"] == 1

    later = copy.deepcopy(snapshot)
    later["variants"]["alpha"] = [
        row for row in later["variants"]["alpha"] if row["variant_id"] != "variant-alpha-archive"
    ]
    reconciled = store.reconcile(later)
    assert reconciled["counts"]["variants"]["stale"] == 1
    archived = db.connection.execute(
        "SELECT active, selectable FROM skill_variants WHERE variant_id=?",
        ("variant-alpha-archive",),
    ).fetchone()
    assert archived is not None
    assert archived["active"] == 0
    assert archived["selectable"] == 0
    assert store.parity(later)["ok"] is True
    db.close()


def test_management_metadata_dry_run_audit_and_no_physical_side_effects(
    tmp_path: Path,
) -> None:
    db, _snapshot, alpha_path = open_seeded(tmp_path)
    service = ManagementService(db)
    body_before = alpha_path.read_text(encoding="utf-8")
    target_path = tmp_path / "must-not-be-created" / "SKILL.md"

    audit_before = service.audit_count()
    category_plan = service.upsert_category("AI", dry_run=True)
    assert category_plan["dry_run"] is True
    assert service.audit_count() == audit_before
    assert db.connection.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"] == 0

    category = service.upsert_category("AI", "AI skills")
    tag = service.upsert_tag("agent")
    service.bind_category("alpha", category["category_id"])
    service.bind_tag("alpha", tag["tag_id"])
    preset = service.upsert_preset("default", ["alpha", "beta"])
    assert service.get_preset(preset["preset_id"])["skill_ids"] == ["alpha", "beta"]

    workspace = service.upsert_workspace("workspace", str(tmp_path), {"scope": "qa"})
    agent = service.upsert_agent("agent", workspace["workspace_id"], {"role": "runner"})
    deployment = service.upsert_deployment(
        "alpha",
        "deploy",
        "planned",
        workspace_id=workspace["workspace_id"],
        agent_id=agent["agent_id"],
        target_path=str(target_path),
    )
    assert service.get_workspace(workspace["workspace_id"])["metadata"] == {"scope": "qa"}
    assert service.get_agent(agent["agent_id"])["metadata"] == {"role": "runner"}
    assert service.get_deployment(deployment["deployment_id"])["state"] == "planned"
    assert alpha_path.read_text(encoding="utf-8") == body_before
    assert not target_path.exists()

    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        service.upsert_preset("invalid", ["missing"], dry_run=True)
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        service.upsert_deployment("missing", "deploy", "planned", dry_run=True)
    with pytest.raises(ValidationError, match="unknown-workspace-id:missing"):
        service.upsert_agent("bad-agent", "missing", dry_run=True)

    service.delete_category(category["category_id"])
    service.delete_tag(tag["tag_id"])
    assert db.connection.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"] == 0
    assert db.connection.execute("SELECT COUNT(*) AS n FROM tags").fetchone()["n"] == 0
    assert service.audit_count() >= audit_before + 10
    db.close()


def test_workflow_planner_bindings_dry_run_and_unknown_skill(tmp_path: Path) -> None:
    db, _snapshot, _ = open_seeded(tmp_path)
    workflows = WorkflowService(db)
    spec = {
        "name": "planner",
        "version": 1,
        "stages": [
            {
                "key": "collect",
                "condition": {"field": "enabled", "equals": True},
                "bindings": [
                    {"key": "required", "skill_id": "alpha", "type": "required"},
                    {"key": "optional", "skill_id": "beta", "type": "optional"},
                    {
                        "key": "conditional",
                        "skill_id": "beta",
                        "type": "conditional",
                        "condition": {"field": "use_beta", "equals": True},
                    },
                ],
            }
        ],
    }
    dry = workflows.create_workflow(spec, dry_run=True)
    assert dry["dry_run"] is True
    assert db.connection.execute("SELECT COUNT(*) AS n FROM workflows").fetchone()["n"] == 0

    created = workflows.create_workflow(spec)
    context = {"enabled": True, "use_beta": True, "include_optional": True}
    plan_one = workflows.plan(created["workflow_id"], context)
    plan_two = workflows.plan(created["workflow_id"], context)
    assert plan_one == plan_two
    assert plan_one["stages"][0]["enabled"] is True
    assert [row["binding_type"] for row in plan_one["stages"][0]["resolved_bindings"]] == [
        "required",
        "optional",
        "conditional",
    ]

    bad = copy.deepcopy(spec)
    bad["name"] = "bad"
    bad["stages"][0]["bindings"][0]["skill_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        workflows.create_workflow(bad, dry_run=True)
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        workflows.create_workflow(bad)
    db.close()


def test_run_retry_skill_fallback_stage_fallback_block_resume_and_reopen(
    tmp_path: Path,
) -> None:
    db, _snapshot, _ = open_seeded(tmp_path)
    workflows = WorkflowService(db)
    workflow = workflows.create_workflow(
        {
            "name": "run-flow",
            "version": 1,
            "stages": [
                {
                    "key": "primary",
                    "retry_limit": 1,
                    "fallback_stage": "fallback",
                    "bindings": [
                        {
                            "key": "worker",
                            "skill_id": "alpha",
                            "type": "required",
                            "fallback_skill_id": "beta",
                        }
                    ],
                },
                {
                    "key": "fallback",
                    "bindings": [{"key": "recovery", "skill_id": "alpha", "type": "required"}],
                },
            ],
        }
    )
    runs = RunService(db)
    run = runs.create_run(workflow["workflow_id"], run_key="fallback-path")
    run = runs.start(run["run_id"])
    assert run["status"] == "active"

    run = runs.fail_current(run["run_id"])
    assert run["stages"][0]["retry_count"] == 1
    run = runs.fail_current(run["run_id"])
    binding = run["stages"][0]["resolved_bindings"][0]
    assert binding["primary_skill_id"] == "alpha"
    assert binding["skill_id"] == "beta"
    assert binding["using_fallback"] is True
    run = runs.fail_current(run["run_id"])
    assert run["current_stage_id"] == workflow["stages"][1]["stage_id"]

    run = runs.block(run["run_id"], "need evidence")
    assert run["status"] == "blocked"
    with pytest.raises(TransitionError, match="resume-requires-evidence"):
        runs.resume(run["run_id"])
    runs.add_evidence(run["run_id"], "gate", {"approved": True}, evidence_key="approval")
    run = runs.resume(run["run_id"])
    assert run["status"] == "active"
    run = runs.succeed_current(run["run_id"])
    assert run["status"] == "completed"
    assert run["terminal_result"] == {"result": "completed"}

    reopen = runs.create_run(workflow["workflow_id"], run_key="reopen")
    reopen = runs.start(reopen["run_id"])
    reopen_id = reopen["run_id"]
    db_path = db.path
    db.close()

    reopened_db = ControlPlaneDB(db_path)
    reopened_runs = RunService(reopened_db)
    recovered = reopened_runs.get_run(reopen_id)
    assert recovered["status"] == "active"
    with pytest.raises(TransitionError, match="illegal-run-transition:active->active"):
        reopened_runs.start(reopen_id)
    reopened_db.close()


def test_run_loop_is_bounded_by_explicit_limit(tmp_path: Path) -> None:
    db, _snapshot, _ = open_seeded(tmp_path)
    workflow = WorkflowService(db).create_workflow(
        {
            "name": "bounded-loop",
            "version": 1,
            "stages": [
                {
                    "key": "loop",
                    "loop_limit": 2,
                    "loop_stop_condition": {"field": "done", "equals": True},
                    "bindings": [{"key": "worker", "skill_id": "alpha", "type": "required"}],
                }
            ],
        }
    )
    runs = RunService(db)
    run = runs.start(
        runs.create_run(
            workflow["workflow_id"],
            {"done": False},
            run_key="bounded-loop",
        )["run_id"]
    )
    run = runs.succeed_current(run["run_id"])
    assert run["stages"][0]["loop_count"] == 1
    assert run["status"] == "active"
    run = runs.succeed_current(run["run_id"])
    assert run["stages"][0]["loop_count"] == 2
    assert run["status"] == "active"
    run = runs.succeed_current(run["run_id"])
    assert run["status"] == "completed"
    db.close()


def test_stage_success_advances_to_next_stage(tmp_path: Path) -> None:
    db, _snapshot, _ = open_seeded(tmp_path)
    workflow = WorkflowService(db).create_workflow(
        {
            "name": "success-next",
            "version": 1,
            "stages": [
                {
                    "key": "first",
                    "bindings": [{"key": "worker", "skill_id": "alpha", "type": "required"}],
                },
                {
                    "key": "second",
                    "bindings": [{"key": "worker", "skill_id": "beta", "type": "required"}],
                },
            ],
        }
    )
    runs = RunService(db)
    run = runs.start(runs.create_run(workflow["workflow_id"], run_key="success-next")["run_id"])
    run = runs.succeed_current(run["run_id"])
    assert run["status"] == "active"
    assert run["current_stage_id"] == workflow["stages"][1]["stage_id"]
    run = runs.succeed_current(run["run_id"])
    assert run["status"] == "completed"
    db.close()
