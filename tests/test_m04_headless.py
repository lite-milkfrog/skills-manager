from __future__ import annotations

import json

from skill_control_plane.run_state import RunService
from skill_control_plane.server import call_tool, headless_tools_schema, tools_schema
from skill_control_plane.workflow import WorkflowService


def test_m04_headless_surface_is_additive_and_narrow() -> None:
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
    names = [tool["name"] for tool in headless_tools_schema()]
    assert names == [
        "workflow_list",
        "workflow_search",
        "workflow_get",
        "workflow_create",
        "workflow_plan",
        "workflow_prompt",
        "run_create",
        "run_get",
        "run_start",
        "run_block",
        "run_evidence_add",
        "run_resume",
        "run_succeed",
        "deployment_plan",
    ]
    assert not any("shell" in name or "exec" in name for name in names)


def test_m04_snapshot_and_illegal_transition_are_typed(seeded) -> None:
    workflow = WorkflowService(seeded["db"]).create_workflow(
        {
            "name": "M04 headless",
            "version": 1,
            "stages": [
                {
                    "key": "verify",
                    "bindings": [{"key": "worker", "skill_id": "one-skill", "type": "required"}],
                }
            ],
        }
    )
    runs = RunService(seeded["db"])
    run_id = runs.create_run(workflow["workflow_id"], run_key="m04")["run_id"]
    runs.start(run_id)
    runs.add_evidence(run_id, "tool", {"read_only": True}, evidence_key="real-tool")
    runs.succeed_current(run_id)

    snapshot = runs.snapshot(run_id)
    assert snapshot["status"] == "completed"
    assert snapshot["evidence"][0]["payload"] == {"read_only": True}
    assert [row["action"] for row in snapshot["audit"]] == [
        "run.create",
        "run.start",
        "run.evidence.add",
        "run.complete",
    ]

    result = call_tool(
        seeded["registry"],
        "run_resume",
        {"run_id": run_id},
        db=seeded["db"],
    )
    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload == {
        "error": "TransitionError",
        "detail": "illegal-resume-transition",
    }
