from __future__ import annotations

import json

from skill_control_plane.server import call_tool
from skill_control_plane.workflow import WorkflowService


def test_workflow_discovery_get_and_recursive_prompt_are_mcp_tools(seeded) -> None:
    workflow = WorkflowService(seeded["db"]).create_workflow(
        {
            "name": "Web development workflow",
            "version": 1,
            "description": "Web development research and delivery workflow",
            "stages": [
                {
                    "key": "web-design",
                    "retry_limit": 2,
                    "bindings": [
                        {
                            "key": "composite",
                            "skill_id": "one-skill",
                            "type": "required",
                            "fallback_skill_id": "fallback-skill",
                        }
                    ],
                }
            ],
        }
    )

    listed = call_tool(
        seeded["registry"],
        "workflow_list",
        {"limit": 20},
        db=seeded["db"],
    )
    listed_payload = json.loads(listed["content"][0]["text"])
    assert listed["isError"] is False
    assert listed_payload["items"][0]["workflow_id"] == workflow["workflow_id"]
    assert listed_payload["items"][0]["stage_count"] == 1
    assert listed_payload["items"][0]["binding_count"] == 1

    searched = call_tool(
        seeded["registry"],
        "workflow_search",
        {"query": "web development", "limit": 20},
        db=seeded["db"],
    )
    searched_payload = json.loads(searched["content"][0]["text"])
    assert searched["isError"] is False
    assert searched_payload["items"][0]["workflow_id"] == workflow["workflow_id"]
    assert "one-skill" in searched_payload["items"][0]["matched_skill_labels"]

    loaded = call_tool(
        seeded["registry"],
        "workflow_get",
        {"workflow_id": workflow["workflow_id"]},
        db=seeded["db"],
    )
    loaded_payload = json.loads(loaded["content"][0]["text"])
    binding = loaded_payload["stages"][0]["bindings"][0]
    assert binding["skill_id"] == "one-skill"
    assert binding["skill_name"] == "one-skill"
    assert binding["fallback_skill_name"] == "fallback-skill"

    prompted = call_tool(
        seeded["registry"],
        "workflow_prompt",
        {"workflow_id": workflow["workflow_id"]},
        db=seeded["db"],
    )
    prompt_payload = json.loads(prompted["content"][0]["text"])
    assert prompted["isError"] is False
    assert "capability entry point" in prompt_payload["prompt"]
    assert "recursively follow its explicit references" in prompt_payload["prompt"]
    assert "Preserve the Skill's internal orchestration" in prompt_payload["prompt"]
    assert "do not flatten" in prompt_payload["prompt"]
    assert "one-skill" in prompt_payload["prompt"]
    assert "fallback-skill" in prompt_payload["prompt"]


def test_bilingual_task_search_resolves_web_capabilities(seeded) -> None:
    web_root = seeded["active"] / "web"
    web_root.mkdir(parents=True, exist_ok=True)
    (web_root / "SKILL.md").write_text(
        (
            "---\n"
            "name: frontend-design\n"
            "description: Production web design and frontend delivery.\n"
            "---\n"
        ),
        encoding="utf-8",
    )
    seeded["registry"].build_index()

    skills = call_tool(
        seeded["registry"],
        "skills_search",
        {"query": "网页设计", "limit": 20},
        db=seeded["db"],
    )
    skills_payload = json.loads(skills["content"][0]["text"])
    assert any(row["skill_id"] == "frontend-design" for row in skills_payload)

    workflow = WorkflowService(seeded["db"]).create_workflow(
        {
            "name": "Web development workflow",
            "version": 1,
            "description": "Frontend web development delivery",
            "stages": [{"key": "frontend", "bindings": [{"key": "web", "skill_id": "one-skill"}]}],
        }
    )
    searched = call_tool(
        seeded["registry"],
        "workflow_search",
        {"query": "网页开发", "limit": 20},
        db=seeded["db"],
    )
    payload = json.loads(searched["content"][0]["text"])
    assert payload["items"][0]["workflow_id"] == workflow["workflow_id"]


def test_skill_resources_and_recursive_resolve_are_mcp_tools(seeded) -> None:
    root = seeded["paths"]["one"].parent
    seeded["paths"]["one"].write_text(
        (
            "---\n"
            "name: one-skill\n"
            "description: Router entry.\n"
            "---\n\n"
            "Read `routes.md`, then use `two-skill` Skill.\n"
        ),
        encoding="utf-8",
    )
    (root / "routes.md").write_text(
        "# routes\nUse `two-skill` Skill.\n",
        encoding="utf-8",
    )

    resources = call_tool(
        seeded["registry"],
        "skills_resources",
        {"name": "one-skill"},
    )
    resources_payload = json.loads(resources["content"][0]["text"])
    assert resources["isError"] is False
    assert resources_payload["resource_count"] == 1
    assert resources_payload["resources"][0]["path"] == "routes.md"

    resolved = call_tool(
        seeded["registry"],
        "skills_resolve",
        {"name": "one-skill", "task": "Primary two", "max_depth": 2},
    )
    payload = json.loads(resolved["content"][0]["text"])
    assert resolved["isError"] is False
    assert payload["resolution"]["analysis"]["followed_resource_paths"] == ["routes.md"]
    assert payload["resolution"]["children"][0]["skill"]["skill_id"] == "two-skill"
    assert payload["summary"]["loaded_skill_count"] == 2
