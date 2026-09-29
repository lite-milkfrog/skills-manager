from __future__ import annotations

import inspect
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from skill_control_plane.management import ManagementService, ValidationError
from skill_control_plane.manager import (
    _SKILL_RESOURCE_MAX_FILE_BYTES,
    ManagerBackend,
    _path_within_root,
)
from skill_control_plane.web_manager import create_server
from skill_control_plane.workflow import WorkflowService


def workflow_spec_m06() -> dict:
    return {
        "name": "M06 view",
        "version": 1,
        "description": "Manager test workflow",
        "stages": [
            {
                "key": "inspect",
                "bindings": [{"key": "worker", "skill_id": "one-skill", "type": "required"}],
            }
        ],
    }


def backend(seeded, opened=None) -> ManagerBackend:
    return ManagerBackend(
        seeded["registry"],
        seeded["db"].path,
        explorer_opener=(opened.append if opened is not None else lambda _path: None),
    )


def test_m06_organization_lists_and_unbind_owner(seeded) -> None:
    service = ManagementService(seeded["db"])
    category = service.upsert_category("Automation", "Metadata only")
    tag = service.upsert_tag("local")
    service.bind_category("one-skill", category["category_id"])
    service.bind_tag("one-skill", tag["tag_id"])

    assert [row["name"] for row in service.list_categories()] == ["Automation"]
    assert [row["name"] for row in service.list_tags()] == ["local"]
    org = service.get_skill_organization("one-skill")
    assert [row["category_id"] for row in org["categories"]] == [category["category_id"]]
    assert [row["tag_id"] for row in org["tags"]] == [tag["tag_id"]]

    service.unbind_category("one-skill", category["category_id"])
    service.unbind_tag("one-skill", tag["tag_id"])
    assert service.get_skill_organization("one-skill") == {
        "skill_id": "one-skill",
        "categories": [],
        "tags": [],
    }


def test_m06_skills_are_paged_metadata_and_body_is_lazy(seeded, monkeypatch) -> None:
    opened: list[Path] = []
    manager = backend(seeded, opened)

    def body_must_not_load(_name: str):
        raise AssertionError("skills_page must not load Skill bodies")

    monkeypatch.setattr(seeded["registry"], "get", body_must_not_load)
    first = manager.skills_page(limit=2)
    assert first["total"] == 4
    assert len(first["items"]) == 2
    assert first["next_cursor"] == 2
    assert "content" not in first["items"][0]

    monkeypatch.undo()
    body = manager.skill_body("one-skill")
    assert "# one-skill" in body["content"]

    result = manager.skill_open_folder("one-skill")
    assert result["skill_id"] == "one-skill"
    assert opened == [seeded["paths"]["one"].parent.absolute()]
    assert list(inspect.signature(manager.skill_open_folder).parameters) == [
        "skill_id",
        "variant_id",
    ]
    with pytest.raises(ValidationError, match="unknown-variant-id"):
        manager.skill_open_folder("one-skill", "not-a-variant")


def test_m06_skill_resources_read_internal_capability_bundle_only(seeded) -> None:
    manager = backend(seeded)
    root = seeded["paths"]["one"].parent
    (root / "routes.md").write_text("# routes\nUse two-skill.\n", encoding="utf-8")
    refs = root / "references"
    refs.mkdir()
    (refs / "workflow.md").write_text(
        "# workflow\nCall Playwright after Coding Tools.\n", encoding="utf-8"
    )
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "handoff.mjs").write_text("export const handoff = true;\n", encoding="utf-8")
    ignored = root / "node_modules" / "pkg"
    ignored.mkdir(parents=True)
    (ignored / "README.md").write_text("must not leak\n", encoding="utf-8")

    bundle = manager.skill_resources("one-skill")
    paths = [row["path"] for row in bundle["resources"]]

    assert bundle["skill_id"] == "one-skill"
    assert paths[:2] == ["routes.md", "references/workflow.md"]
    assert "scripts/handoff.mjs" in paths
    assert all("node_modules" not in path for path in paths)
    assert bundle["resource_count"] == 3
    assert bundle["truncated"] is False
    assert bundle["resources"][0]["type"] == "markdown"
    assert bundle["resources"][0]["truncated"] is False


def test_skill_resolve_follows_explicit_resources_and_child_skills(seeded) -> None:
    manager = backend(seeded)
    root = seeded["paths"]["one"].parent
    seeded["paths"]["one"].write_text(
        (
            "---\n"
            "name: one-skill\n"
            "description: Router entry.\n"
            "---\n\n"
            "# one-skill\n"
            "Read `references/routes.md` before execution.\n"
        ),
        encoding="utf-8",
    )
    refs = root / "references"
    refs.mkdir()
    (refs / "routes.md").write_text(
        ("# routes\nUse `two-skill` Skill for this route.\nThen read `references/execution.md`.\n"),
        encoding="utf-8",
    )
    (refs / "execution.md").write_text(
        (
            "# execution\n"
            "Run `scripts/worker.py`.\n"
            "This document mentions `three-skill` as an example, not as a child Skill.\n"
        ),
        encoding="utf-8",
    )
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "worker.py").write_text("print('ok')\n", encoding="utf-8")

    resolved = manager.skill_resolve(
        "one-skill",
        task="Primary two",
        max_depth=2,
    )
    node = resolved["resolution"]

    assert node["skill"]["skill_id"] == "one-skill"
    assert "# one-skill" in node["skill"]["content"]
    assert node["analysis"]["kind"] == "router"
    assert node["analysis"]["followed_resource_paths"] == [
        "references/routes.md",
        "references/execution.md",
        "scripts/worker.py",
    ]
    assert [row["skill_id"] for row in node["analysis"]["candidate_children"]] == ["two-skill"]
    assert node["children"][0]["skill"]["skill_id"] == "two-skill"
    assert "# two-skill" in node["children"][0]["skill"]["content"]
    assert resolved["summary"]["loaded_skill_count"] == 2
    assert resolved["summary"]["unresolved_child_skills"] == []
    assert resolved["contract"]["no_flatten"] is True


def test_m11_skill_resource_root_containment_and_single_file_cap(seeded, tmp_path) -> None:
    manager = backend(seeded)
    root = seeded["paths"]["one"].parent.resolve()
    outside = (tmp_path / "outside.md").resolve()
    outside.write_text("outside secret", encoding="utf-8")

    assert _path_within_root((root / "references" / "route.md").resolve(), root)
    assert not _path_within_root(outside, root)

    (root / "unsupported.bin").write_bytes(b"not text")
    oversized = root / "oversized.md"
    oversized.write_text("x" * (_SKILL_RESOURCE_MAX_FILE_BYTES + 1), encoding="utf-8")

    bundle = manager.skill_resources("one-skill")
    resource_paths = {row["path"] for row in bundle["resources"]}
    skipped = {row["path"]: row["reason"] for row in bundle["skipped"]}

    assert "unsupported.bin" not in resource_paths
    assert "oversized.md" not in resource_paths
    assert skipped["oversized.md"] == "file-too-large"
    assert bundle["truncated"] is True


def test_m11_skill_resource_total_cap_is_bounded(seeded) -> None:
    manager = backend(seeded)
    root = seeded["paths"]["one"].parent.resolve()
    for index in range(5):
        (root / f"bulk-{index}.md").write_text("y" * (240 * 1024), encoding="utf-8")

    bundle = manager.skill_resources("one-skill")

    assert bundle["total_bytes"] <= 1024 * 1024
    assert bundle["resource_count"] <= 64
    assert bundle["truncated"] is True


def test_workflow_family_listing_spans_service_page_boundary(seeded) -> None:
    service = WorkflowService(seeded["db"])
    for version in range(1, 202):
        spec = workflow_spec_m06()
        spec["version"] = version
        service.create_workflow(spec)

    manager = backend(seeded)
    page = manager.workflow_list(name="M06 view", limit=200, include_archived=True)
    assert page["total"] == 201
    assert page["next_cursor"] == 200
    assert manager.workflow_list(
        name="M06 view", cursor=200, include_archived=True
    )["items"][0]["version"] == 1


def test_m06_workflow_run_and_runtime_read_adapters(seeded, monkeypatch) -> None:
    workflow = WorkflowService(seeded["db"]).create_workflow(workflow_spec_m06())
    manager = backend(seeded)

    workflows = manager.workflow_list(limit=20)
    assert workflows["total"] == 1
    assert workflows["items"][0]["workflow_id"] == workflow["workflow_id"]
    assert manager.workflow_get(workflow["workflow_id"])["stages"][0]["key"] == "inspect"

    run = manager.run_create(workflow["workflow_id"], {"task": "inspect"}, run_key="m06")
    runs = manager.run_list(status="planned", skill_id="one-skill")
    assert runs["total"] == 1
    assert runs["items"][0]["run_id"] == run["run_id"]

    assert manager.deployment_transactions_list()["items"] == []
    assert manager.managed_locations_list()["items"] == []

    monkeypatch.setattr(manager, "_port_open", lambda _port: True)
    health = manager.runtime_health()
    assert health["mutations_allowed"] is True
    assert health["parity"]["ok"] is True
    assert health["integrity"]["integrity_check"] == ["ok"]
    assert health["integrity"]["foreign_key_violations"] == []
    assert health["integrity"]["schema_version"] == 4


def test_workflow_http_archive_restore_and_delete_gate(seeded) -> None:
    workflow_id = WorkflowService(seeded["db"]).create_workflow(workflow_spec_m06())[
        "workflow_id"
    ]
    server = create_server(
        "127.0.0.1", 0, registry=seeded["registry"], db_path=seeded["db"].path,
        explorer_opener=lambda _path: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}/api/workflows/{workflow_id}"

    def post(suffix: str, body: dict) -> dict:
        request = urllib.request.Request(
            base + suffix, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read())

    try:
        with urllib.request.urlopen(base + "/usage", timeout=2) as response:
            assert json.loads(response.read())["run_count"] == 0
        with pytest.raises(urllib.error.HTTPError) as exc:
            post("/delete", {"confirm": True})
        assert exc.value.code == 400
        assert post("/archive", {})["archived"] is True
        with pytest.raises(urllib.error.HTTPError) as exc:
            post("/delete", {})
        assert exc.value.code == 400
        assert post("/restore", {})["archived"] is False
        assert post("/archive", {})["archived"] is True
        assert post("/delete", {"confirm": True})["deleted"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_skill_navigation_contract() -> None:
    web_root = Path(__file__).resolve().parents[1] / "web" / "manager"
    app = (web_root / "app.js").read_text(encoding="utf-8")
    styles = (web_root / "styles.css").read_text(encoding="utf-8")

    assert "renderSkillDetail(parts[1], parts[2] || 'about', query)" in app
    assert "routeQuery.get('from_workflow')" in app
    assert "Back to workflow" in app
    assert "返回工作流" in app
    assert "workflowSkillHref" in app
    assert "'<a class=\"workflow-skill-token\" href=\"' + workflowSkillHref(skillId)" in app
    assert "a.workflow-skill-token:hover" in styles
    assert "a.workflow-skill-token:focus-visible" in styles


def test_web_manager_typed_api_and_no_physical_apply(seeded) -> None:
    web_root = Path(__file__).resolve().parents[1] / "web" / "manager"
    server = create_server(
        "127.0.0.1",
        0,
        registry=seeded["registry"],
        db_path=seeded["db"].path,
        web_root=web_root,
        explorer_opener=lambda _path: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/#/skills", timeout=2) as response:
            assert "Skill Control Plane" in response.read().decode("utf-8")

        with urllib.request.urlopen(base + "/api/skills?limit=2", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert len(payload["items"]) == 2
        assert "content" not in payload["items"][0]

        skill_root = seeded["paths"]["one"].parent
        (skill_root / "routes.md").write_text("# routes\nUse two-skill.\n", encoding="utf-8")
        with urllib.request.urlopen(
            base + "/api/skills/one-skill/resources", timeout=2
        ) as response:
            resources = json.loads(response.read().decode("utf-8"))
        assert resources["skill_id"] == "one-skill"
        assert resources["resources"][0]["path"] == "routes.md"

        request = urllib.request.Request(
            base + "/api/deployments/apply",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=2)
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
