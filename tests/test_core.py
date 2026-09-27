from __future__ import annotations

import json
from pathlib import Path

from skill_control_plane import core
from skill_control_plane.core import Registry, SourceRoot
from skill_control_plane.server import call_tool


def _skill(root: Path, folder: str, name: str, description: str) -> Path:
    target = root / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


def test_project_portable_wins_independent_of_scan_order(tmp_path: Path) -> None:
    portable = tmp_path / ".skills"
    agents = tmp_path / ".agents" / "skills"
    archive = tmp_path / "final-acceptance" / "venv" / "skills"
    winner = _skill(portable, "webgpt-as-codex", "webgpt-as-codex", "Portable canonical.")
    _skill(agents, "webgpt-as-codex", "webgpt-as-codex", "Shared active.")
    archived = _skill(archive, "webgpt-as-codex", "webgpt-as-codex", "Historical copy.")

    roots = [
        SourceRoot("shared_agents", agents, 900),
        SourceRoot("project_portable", portable, 1000),
    ]
    registry = Registry(roots, [archived])
    payload = registry.build_index()

    selected = registry.find("webgpt-as-codex")
    assert selected is not None
    assert Path(selected["path"]) == winner.absolute()
    assert selected["source_class"] == "project_portable"
    assert selected["authority_tier"] == 1000

    variants = payload["variants"]["webgpt-as-codex"]
    assert len(variants) == 3
    archive_row = next(row for row in variants if "final-acceptance" in row["path"])
    assert archive_row["selectable"] is False
    assert archive_row["source_class"] == "historical_archive"


def test_explicit_historical_variant_is_preserved_but_cannot_beat_active(
    tmp_path: Path,
) -> None:
    active = tmp_path / "state" / "Skills"
    historical = tmp_path / "old-scan"
    selected_path = _skill(active, "fund", "fund-writing", "Active fund skill.")
    old_path = _skill(historical, "fund", "fund-writing", "Old scan copy.")

    registry = Registry(
        [SourceRoot("state_skills", active, 700)],
        [old_path],
    )
    registry.build_index()

    selected = registry.find("fund-writing")
    assert selected is not None
    assert Path(selected["path"]) == selected_path.absolute()
    variants = registry.variants_for("fund-writing")
    assert {row["source_class"] for row in variants} == {
        "state_skills",
        "historical_explicit",
    }


def test_same_tier_tie_break_is_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    a = _skill(left, "same", "same-skill", "Left.")
    b = _skill(right, "same", "same-skill", "Right.")

    roots_one = [
        SourceRoot("configured_active", right, 600),
        SourceRoot("configured_active", left, 600),
    ]
    roots_two = list(reversed(roots_one))
    first = Registry(roots_one)
    second = Registry(roots_two)
    first.build_index()
    second.build_index()
    assert first.find("same-skill")["path"] == second.find("same-skill")["path"]
    assert first.find("same-skill")["path"] == str(min(a.absolute(), b.absolute()))


def test_metadata_first_list_and_full_get_on_demand(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _skill(root, "one", "one-skill", "One skill.")
    registry = Registry([SourceRoot("configured_active", root, 600)])
    registry.build_index()

    result = call_tool(registry, "skills_list", {"limit": 20})
    body = json.loads(result["content"][0]["text"])
    assert body[0]["name"] == "one-skill"
    assert "content" not in body[0]

    loaded = registry.get("one-skill")
    assert "# one-skill" in loaded["content"]
    assert len(loaded["variants"]) == 1


def test_category_router_metadata(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    path = _skill(root, "category-web-ui", "category-web-ui", "Route web UI work.")
    routes = path.parent / "references" / "routes.md"
    routes.parent.mkdir()
    routes.write_text("# routes\n", encoding="utf-8")
    registry = Registry([SourceRoot("shared_agents", root, 900)])
    registry.build_index()
    assert registry.find("category-web-ui")["category_router"] is True


def test_default_registry_uses_real_config_for_explicit_user_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "user"
    config = home / "AppData" / "Local" / "WebGPT-as-Codex" / "skills" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"schema_version": 1, "roots": [], "files": []}\n', encoding="utf-8")
    monkeypatch.setenv("SKILL_CONTROL_PLANE_USER_HOME", str(home))

    registry = core.build_default_registry()

    assert registry.legacy_config_path == config.absolute()
    agents = next(root for root in registry.roots if root.source_class == "shared_agents")
    assert agents.path == (home / ".agents" / "skills").absolute()
