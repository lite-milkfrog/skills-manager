from __future__ import annotations

import pytest

from skill_control_plane.management import ValidationError
from skill_control_plane.run_state import RunService, TransitionError
from skill_control_plane.storage import ControlPlaneDB
from skill_control_plane.workflow import WorkflowService


def workflow_spec() -> dict:
    return {
        "name": "M02 acceptance",
        "version": 1,
        "stages": [
            {
                "key": "work",
                "retry_limit": 1,
                "fallback_stage": "recover",
                "bindings": [
                    {
                        "key": "primary",
                        "skill_id": "one-skill",
                        "type": "required",
                        "fallback_skill_id": "fallback-skill",
                    },
                    {
                        "key": "optional",
                        "skill_id": "two-skill",
                        "type": "optional",
                    },
                    {
                        "key": "conditional",
                        "skill_id": "three-skill",
                        "type": "conditional",
                        "condition": {"field": "flags.use_three", "equals": True},
                    },
                ],
            },
            {
                "key": "recover",
                "bindings": [
                    {
                        "key": "recovery",
                        "skill_id": "fallback-skill",
                        "type": "required",
                    }
                ],
            },
            {
                "key": "finish",
                "bindings": [{"key": "final", "skill_id": "one-skill", "type": "required"}],
            },
        ],
    }


def test_workflow_archive_preserves_runs_and_version_history(seeded) -> None:
    db = seeded["db"]
    workflows = WorkflowService(db)
    first = workflows.create_workflow(workflow_spec())
    workflow_id = first["workflow_id"]
    run = RunService(db).create_run(workflow_id, run_key="archive-history")
    workflows.archive_workflow(workflow_id)

    assert workflows.get_workflow(workflow_id)["archived"] is True
    assert workflows.workflow_usage(workflow_id)["run_count"] == 1
    assert RunService(db).get_run(run["run_id"])["workflow_id"] == workflow_id
    with pytest.raises(ValidationError, match="archived-workflow-cannot-start-new-run"):
        RunService(db).create_run(workflow_id, run_key="after-archive")
    with pytest.raises(ValidationError, match="workflow-delete-requires"):
        workflows.delete_workflow_permanently(workflow_id)

    second_spec = workflow_spec()
    second_spec["version"] = 2
    second = workflows.create_workflow(second_spec)
    assert second["version"] == 2
    all_items = workflows.list_workflows(include_archived=True)["items"]
    assert [item["version"] for item in all_items] == [2, 1]
    assert [item["version"] for item in workflows.list_workflows()["items"]] == [2]
    assert workflows.restore_workflow(workflow_id)["archived"] is False
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_workflow_permanent_delete_requires_archived_and_zero_run(seeded) -> None:
    db = seeded["db"]
    workflows = WorkflowService(db)
    workflow_id = workflows.create_workflow(workflow_spec())["workflow_id"]
    with pytest.raises(ValidationError, match="workflow-delete-requires"):
        workflows.delete_workflow_permanently(workflow_id)
    workflows.archive_workflow(workflow_id)
    assert workflows.workflow_usage(workflow_id)["can_delete"] is True
    assert workflows.delete_workflow_permanently(workflow_id)["deleted"] is True
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    actions = [row[0] for row in db.connection.execute("SELECT action FROM audit_log")]
    assert "workflow.archive" in actions and "workflow.delete" in actions


def test_workflow_create_read_and_deterministic_binding_resolution(seeded) -> None:
    service = WorkflowService(seeded["db"])
    created = service.create_workflow(workflow_spec())
    loaded = service.get_workflow(created["workflow_id"])
    assert [stage["key"] for stage in loaded["stages"]] == [
        "work",
        "recover",
        "finish",
    ]

    context = {"flags": {"use_three": True}}
    first = service.plan(created["workflow_id"], context)
    second = service.plan(created["workflow_id"], context)
    assert first == second
    bindings = first["stages"][0]["resolved_bindings"]
    assert [row["binding_key"] for row in bindings] == ["primary", "conditional"]

    all_bindings = service.plan(
        created["workflow_id"],
        {"flags": {"use_three": True}, "include_optional": True},
    )["stages"][0]["resolved_bindings"]
    assert [row["binding_key"] for row in all_bindings] == [
        "primary",
        "optional",
        "conditional",
    ]


def test_workflow_stage_semantics_are_persisted_planned_and_prompted(seeded) -> None:
    service = WorkflowService(seeded["db"])
    workflow = service.create_workflow(
        {
            "name": "Semantic stages",
            "version": 1,
            "description": "Build with explicit human-readable stage intent.",
            "stages": [
                {
                    "key": "research",
                    "title": "Research before building",
                    "description": "Understand existing work and avoid duplicate implementation.",
                    "instructions": (
                        "Inspect the current project, compare reusable options, "
                        "and record why the selected approach is appropriate."
                    ),
                    "expected_output": "A short evidence-backed implementation plan.",
                    "completion_criteria": (
                        "The reusable path is identified and open questions are resolved."
                    ),
                    "bindings": [
                        {
                            "key": "primary",
                            "skill_id": "one-skill",
                            "type": "required",
                        }
                    ],
                }
            ],
        }
    )

    loaded = service.get_workflow(workflow["workflow_id"])
    stage = loaded["stages"][0]
    assert stage["title"] == "Research before building"
    assert stage["description"].startswith("Understand existing work")
    assert stage["instructions"].startswith("Inspect the current project")
    assert stage["expected_output"].startswith("A short evidence-backed")
    assert stage["completion_criteria"].startswith("The reusable path")

    planned = service.plan(workflow["workflow_id"])
    assert planned["stages"][0]["title"] == stage["title"]
    assert planned["stages"][0]["instructions"] == stage["instructions"]

    prompt = service.prompt(workflow["workflow_id"])["prompt"]
    assert "Research before building" in prompt
    assert "Purpose: Understand existing work" in prompt
    assert "Agent instructions: Inspect the current project" in prompt
    assert "Expected output: A short evidence-backed" in prompt
    assert "Completion criteria: The reusable path" in prompt


def test_workflow_unknown_skill_and_dry_run_do_not_mutate(seeded) -> None:
    service = WorkflowService(seeded["db"])
    spec = workflow_spec()
    spec["name"] = "Dry"
    before = seeded["db"].connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    plan = service.create_workflow(spec, dry_run=True)
    after = seeded["db"].connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    assert plan["dry_run"] is True
    assert before == after

    bad = workflow_spec()
    bad["name"] = "Bad"
    bad["stages"][0]["bindings"][0]["skill_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        service.create_workflow(bad)


def test_run_retry_skill_fallback_stage_fallback_block_resume_and_reopen(
    seeded,
) -> None:
    workflow = WorkflowService(seeded["db"]).create_workflow(workflow_spec())
    runs = RunService(seeded["db"])
    run = runs.create_run(
        workflow["workflow_id"],
        {"flags": {"use_three": False}},
        run_key="durable",
    )
    run_id = run["run_id"]
    assert run["status"] == "planned"

    active = runs.start(run_id)
    assert active["status"] == "active"
    assert active["stages"][0]["status"] == "running"

    retry = runs.fail_current(run_id, {"passed": False, "reason": "first"})
    assert retry["stages"][0]["retry_count"] == 1
    assert retry["stages"][0]["status"] == "running"

    skill_fallback = runs.fail_current(run_id, {"passed": False, "reason": "second"})
    binding = skill_fallback["stages"][0]["resolved_bindings"][0]
    assert binding["using_fallback"] is True
    assert binding["skill_id"] == "fallback-skill"

    stage_fallback = runs.fail_current(run_id, {"passed": False, "reason": "third"})
    assert stage_fallback["stages"][0]["status"] == "failed"
    assert stage_fallback["stages"][1]["status"] == "running"

    after_recovery = runs.succeed_current(run_id)
    assert after_recovery["stages"][2]["status"] == "running"

    blocked = runs.block(run_id, "need operator evidence")
    assert blocked["status"] == "blocked"
    with pytest.raises(TransitionError, match="resume-requires-evidence"):
        runs.resume(run_id)

    runs.add_evidence(run_id, "operator", {"approved": True}, evidence_key="approval")

    db_path = seeded["db"].path
    seeded["db"].close()
    reopened = ControlPlaneDB(db_path)
    resumed_runs = RunService(reopened)
    resumed = resumed_runs.resume(run_id)
    assert resumed["status"] == "active"
    completed = resumed_runs.succeed_current(run_id)
    assert completed["status"] == "completed"
    assert completed["terminal_result"]["result"] == "completed"

    with pytest.raises(TransitionError, match="illegal-run-transition"):
        resumed_runs.start(run_id)
    reopened.close()

    # Keep fixture teardown safe after explicit reopen/close.
    seeded["db"].connection = ControlPlaneDB(db_path).connection


def test_bounded_loop_stops_at_explicit_limit(seeded) -> None:
    service = WorkflowService(seeded["db"])
    workflow = service.create_workflow(
        {
            "name": "Loop",
            "version": 1,
            "stages": [
                {
                    "key": "loop",
                    "loop_limit": 1,
                    "loop_stop_condition": {"field": "done", "equals": True},
                    "bindings": [
                        {
                            "key": "primary",
                            "skill_id": "one-skill",
                            "type": "required",
                        }
                    ],
                }
            ],
        }
    )
    runs = RunService(seeded["db"])
    run_id = runs.create_run(workflow["workflow_id"], {"done": False})["run_id"]
    runs.start(run_id)
    looped = runs.succeed_current(run_id)
    assert looped["status"] == "active"
    assert looped["stages"][0]["loop_count"] == 1
    completed = runs.succeed_current(run_id)
    assert completed["status"] == "completed"


def test_invalid_transition_rejected(seeded) -> None:
    workflow = WorkflowService(seeded["db"]).create_workflow(
        {
            "name": "Invalid transition",
            "version": 1,
            "stages": [
                {
                    "key": "one",
                    "bindings": [
                        {
                            "key": "primary",
                            "skill_id": "one-skill",
                            "type": "required",
                        }
                    ],
                }
            ],
        }
    )
    runs = RunService(seeded["db"])
    run_id = runs.create_run(workflow["workflow_id"])["run_id"]
    with pytest.raises(TransitionError, match="illegal-stage-success-transition"):
        runs.succeed_current(run_id)
