from __future__ import annotations

from pathlib import Path

import pytest

from skill_control_plane.core import Registry, SourceRoot
from skill_control_plane.registry_store import RegistryStore
from skill_control_plane.storage import ControlPlaneDB


def write_skill(root: Path, folder: str, name: str, description: str) -> Path:
    target = root / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def seeded(tmp_path: Path):
    active = tmp_path / ".skills"
    shared = tmp_path / ".agents" / "skills"
    archive = tmp_path / "archive" / "skills"

    paths = {
        "one": write_skill(active, "one", "one-skill", "Primary one."),
        "two": write_skill(active, "two", "two-skill", "Primary two."),
        "three": write_skill(shared, "three", "three-skill", "Conditional three."),
        "fallback": write_skill(active, "fallback", "fallback-skill", "Fallback."),
        "archive": write_skill(archive, "one-copy", "one-skill", "Historical one."),
    }
    registry = Registry(
        [
            SourceRoot("project_portable", active, 1000),
            SourceRoot("shared_agents", shared, 900),
        ],
        [paths["archive"]],
    )
    snapshot = registry.build_index()
    db = ControlPlaneDB(tmp_path / "control-plane.db")
    store = RegistryStore(db)
    store.reconcile(snapshot)
    yield {
        "db": db,
        "store": store,
        "snapshot": snapshot,
        "registry": registry,
        "paths": paths,
        "active": active,
        "shared": shared,
    }
    db.close()
