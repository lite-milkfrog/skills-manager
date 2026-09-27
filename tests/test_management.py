from __future__ import annotations

from pathlib import Path

import pytest

from skill_control_plane.management import ManagementService, ValidationError


def test_categories_tags_crud_and_audit(seeded) -> None:
    db = seeded["db"]
    service = ManagementService(db)
    audit_before = service.audit_count()

    plan = service.upsert_category("Automation", "Workflow tools", dry_run=True)
    assert plan["dry_run"] is True
    assert service.audit_count() == audit_before
    assert db.connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0

    category = service.upsert_category("Automation", "Workflow tools")
    assert service.get_category(category["category_id"])["description"] == "Workflow tools"
    updated = service.upsert_category("Automation", "Updated")
    assert updated["category_id"] == category["category_id"]
    assert service.get_category(category["category_id"])["description"] == "Updated"

    tag = service.upsert_tag("local")
    assert service.get_tag(tag["tag_id"])["name"] == "local"
    service.bind_category("one-skill", category["category_id"])
    service.bind_tag("one-skill", tag["tag_id"])

    service.delete_tag(tag["tag_id"])
    service.delete_category(category["category_id"])
    with pytest.raises(ValidationError, match="unknown-tag-id"):
        service.get_tag(tag["tag_id"])
    with pytest.raises(ValidationError, match="unknown-category-id"):
        service.get_category(category["category_id"])
    assert service.audit_count() > audit_before


def test_preset_requires_canonical_skill_and_round_trips(seeded) -> None:
    service = ManagementService(seeded["db"])
    preset = service.upsert_preset("Core", ["one-skill", "two-skill"])
    loaded = service.get_preset(preset["preset_id"])
    assert loaded["skill_ids"] == ["one-skill", "two-skill"]

    before = service.audit_count()
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        service.upsert_preset("Bad", ["missing"], dry_run=True)
    assert service.audit_count() == before


def test_workspace_agent_deployment_metadata_only_no_physical_side_effect(
    seeded, tmp_path: Path
) -> None:
    service = ManagementService(seeded["db"])
    target = tmp_path / "must-not-be-created" / "SKILL.md"

    workspace = service.upsert_workspace("Local", str(tmp_path), {"kind": "test"})
    agent = service.upsert_agent("Agent A", workspace["workspace_id"], {"profile": "local"})
    dry = service.upsert_deployment(
        "one-skill",
        "deploy",
        "planned",
        workspace_id=workspace["workspace_id"],
        agent_id=agent["agent_id"],
        target_path=str(target),
        dry_run=True,
    )
    assert dry["dry_run"] is True
    assert not target.exists()

    deployment = service.upsert_deployment(
        "one-skill",
        "deploy",
        "planned",
        workspace_id=workspace["workspace_id"],
        agent_id=agent["agent_id"],
        target_path=str(target),
        metadata={"physical": False},
    )
    assert service.get_workspace(workspace["workspace_id"])["metadata"]["kind"] == "test"
    assert service.get_agent(agent["agent_id"])["workspace_id"] == workspace["workspace_id"]
    loaded = service.get_deployment(deployment["deployment_id"])
    assert loaded["skill_id"] == "one-skill"
    assert loaded["state"] == "planned"
    assert not target.exists()

    sources = service.list_sources()
    assert any(row["source_class"] == "project_portable" and row["active"] for row in sources)


def test_unknown_skill_rejected_for_deployment(seeded) -> None:
    service = ManagementService(seeded["db"])
    with pytest.raises(ValidationError, match="unknown-skill-id:missing"):
        service.upsert_deployment("missing", "deploy", "planned")
