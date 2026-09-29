from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from skill_control_plane.core import build_default_registry
from skill_control_plane.registry_store import RegistryStore
from skill_control_plane.storage import ControlPlaneDB
from skill_control_plane.workflow import WorkflowService


def _ensure_production_user_home() -> None:
    if os.getenv("SKILLS_MANAGER_USER_HOME") or os.getenv(
        "SKILL_CONTROL_PLANE_USER_HOME"
    ):
        return
    if os.name != "nt":
        return
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 40, None, 0, buffer)
    if result == 0 and buffer.value:
        os.environ["SKILLS_MANAGER_USER_HOME"] = buffer.value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default=str(ROOT / "runtime" / "state" / "control-plane.db"),
    )
    parser.add_argument("--archive-older", action="store_true")
    args = parser.parse_args()

    _ensure_production_user_home()
    registry = build_default_registry()
    snapshot = registry.payload(force=True)
    workflow_files = sorted((ROOT / "workflows").glob("*.json"))

    with ControlPlaneDB(Path(args.db)) as db:
        RegistryStore(db).reconcile(
            snapshot,
            legacy_config_path=registry.legacy_config_path,
        )
        service = WorkflowService(db)
        created: list[str] = []
        production: dict[str, int] = {}

        for path in workflow_files:
            spec = json.loads(path.read_text(encoding="utf-8"))
            production[str(spec["name"])] = max(
                int(spec["version"]),
                production.get(str(spec["name"]), 0),
            )
            try:
                result = service.create_workflow(spec)
                created.append(str(result["workflow_id"]))
            except Exception as exc:
                if "workflow-already-exists" not in str(exc):
                    raise

        archived: list[str] = []
        if args.archive_older:
            with db.transaction() as conn:
                rows = conn.execute(
                    "SELECT workflow_id,name,version FROM workflows WHERE active=1"
                ).fetchall()
                for row in rows:
                    latest = production.get(str(row["name"]))
                    if latest is None or int(row["version"]) >= latest:
                        continue
                    conn.execute(
                        "UPDATE workflows SET active=0 WHERE workflow_id=?",
                        (row["workflow_id"],),
                    )
                    db.audit(
                        conn,
                        "workflow.archive.import",
                        "workflow",
                        str(row["workflow_id"]),
                        {
                            "name": row["name"],
                            "version": int(row["version"]),
                            "reason": "superseded-by-versioned-production-spec",
                        },
                    )
                    archived.append(str(row["workflow_id"]))

    print(
        json.dumps(
            {"ok": True, "created": created, "archived": archived},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
