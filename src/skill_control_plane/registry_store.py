from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .storage import ControlPlaneDB, utc_now


def _source_key(source_class: str, path: str, authority_tier: int, selectable: bool) -> str:
    material = f"{source_class}\0{Path(path)}\0{authority_tier}\0{int(selectable)}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


class RegistryStore:
    def __init__(self, db: ControlPlaneDB) -> None:
        self.db = db
        self.db.migrate()

    @staticmethod
    def _selected_by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(row["skill_id"]): row
            for row in snapshot.get("skills", [])
            if isinstance(row, dict) and row.get("skill_id")
        }

    @staticmethod
    def _variants(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        variants = snapshot.get("variants", {})
        if not isinstance(variants, dict):
            return rows
        for skill_id in sorted(variants):
            entries = variants.get(skill_id, [])
            if not isinstance(entries, list):
                continue
            for row in entries:
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    def plan_reconcile(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "dry_run": True,
            "action": "registry.reconcile",
            "diff": self.parity(snapshot),
        }

    def reconcile(
        self,
        snapshot: dict[str, Any],
        *,
        legacy_config_path: Path | str | None = None,
    ) -> dict[str, Any]:
        selected = self._selected_by_id(snapshot)
        variants = self._variants(snapshot)
        run_id = hashlib.sha256(
            json.dumps(
                {
                    "skills": [
                        (k, selected[k].get("variant_id"), selected[k].get("sha256"))
                        for k in sorted(selected)
                    ],
                    "variants": [
                        (v.get("variant_id"), v.get("path"), v.get("sha256")) for v in variants
                    ],
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()[:24]
        compatibility: dict[str, Any] = {"legacy_config_path": None}
        if legacy_config_path is not None:
            path = Path(legacy_config_path).expanduser().absolute()
            compatibility["legacy_config_path"] = str(path)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                compatibility["legacy_roots"] = (
                    len(payload.get("roots", [])) if isinstance(payload, dict) else 0
                )
                compatibility["legacy_files"] = (
                    len(payload.get("files", [])) if isinstance(payload, dict) else 0
                )
            except (OSError, json.JSONDecodeError):
                compatibility["read_error"] = True

        counts = {
            "sources": {"added": 0, "updated": 0, "unchanged": 0, "stale": 0},
            "skills": {"added": 0, "updated": 0, "unchanged": 0, "stale": 0},
            "variants": {"added": 0, "updated": 0, "unchanged": 0, "stale": 0},
        }
        now = utc_now()
        with self.db.transaction() as conn:
            old_active_sources = {
                row["source_key"]
                for row in conn.execute("SELECT source_key FROM sources WHERE active=1")
            }
            old_active_skills = {
                row["skill_id"]
                for row in conn.execute("SELECT skill_id FROM skills WHERE active=1")
            }
            old_active_variants = {
                row["variant_id"]
                for row in conn.execute("SELECT variant_id FROM skill_variants WHERE active=1")
            }

            source_ids: dict[tuple[str, str, int, bool], int] = {}
            seen_source_keys: set[str] = set()
            for variant in variants:
                source_tuple = (
                    str(variant.get("source_class", "")),
                    str(variant.get("root", "")),
                    int(variant.get("authority_tier", 0)),
                    bool(variant.get("selectable", False)),
                )
                if source_tuple in source_ids:
                    continue
                source_class, path, tier, selectable = source_tuple
                key = _source_key(source_class, path, tier, selectable)
                seen_source_keys.add(key)
                existing = conn.execute(
                    "SELECT * FROM sources WHERE source_key=?", (key,)
                ).fetchone()
                values = (source_class, path, tier, int(selectable))
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO sources(
                            source_key, source_class, path, authority_tier, selectable,
                            active, last_seen_run, created_at, updated_at
                        ) VALUES(?,?,?,?,?,1,?,?,?)
                        """,
                        (key, *values, run_id, now, now),
                    )
                    counts["sources"]["added"] += 1
                else:
                    current = (
                        existing["source_class"],
                        existing["path"],
                        int(existing["authority_tier"]),
                        int(existing["selectable"]),
                    )
                    if current == values and int(existing["active"]) == 1:
                        counts["sources"]["unchanged"] += 1
                    else:
                        counts["sources"]["updated"] += 1
                    conn.execute(
                        """
                        UPDATE sources SET source_class=?, path=?, authority_tier=?,
                            selectable=?, active=1, last_seen_run=?, updated_at=?
                        WHERE source_key=?
                        """,
                        (*values, run_id, now, key),
                    )
                source_row = conn.execute(
                    "SELECT source_id FROM sources WHERE source_key=?", (key,)
                ).fetchone()
                source_ids[source_tuple] = int(source_row["source_id"])

            for skill_id in sorted(selected):
                row = selected[skill_id]
                existing = conn.execute(
                    "SELECT * FROM skills WHERE skill_id=?", (skill_id,)
                ).fetchone()
                values = (
                    str(row.get("name", skill_id)),
                    str(row.get("description", "")),
                    str(row.get("variant_id", "")),
                    int(bool(row.get("category_router", False))),
                )
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO skills(
                            skill_id, name, description, selected_variant_id, category_router,
                            active, first_seen_at, last_seen_at, updated_at
                        ) VALUES(?,?,?,?,?,1,?,?,?)
                        """,
                        (skill_id, *values, now, now, now),
                    )
                    counts["skills"]["added"] += 1
                else:
                    current = (
                        existing["name"],
                        existing["description"],
                        existing["selected_variant_id"] or "",
                        int(existing["category_router"]),
                    )
                    if current == values and int(existing["active"]) == 1:
                        counts["skills"]["unchanged"] += 1
                    else:
                        counts["skills"]["updated"] += 1
                    conn.execute(
                        """
                        UPDATE skills SET name=?, description=?, selected_variant_id=?,
                            category_router=?, active=1, last_seen_at=?, updated_at=?
                        WHERE skill_id=?
                        """,
                        (*values, now, now, skill_id),
                    )

            # Historical variant-only identities are retained as inactive skill shells so
            # their variants remain referentially valid without becoming selectable.
            variant_skill_ids = {
                str(row.get("skill_id", "")) for row in variants if row.get("skill_id")
            }
            for skill_id in sorted(variant_skill_ids - set(selected)):
                existing = conn.execute(
                    "SELECT skill_id FROM skills WHERE skill_id=?", (skill_id,)
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO skills(
                            skill_id, name, description, selected_variant_id, category_router,
                            active, first_seen_at, last_seen_at, updated_at
                        ) VALUES(?,?,?,?,?,0,?,?,?)
                        """,
                        (skill_id, skill_id, "", None, 0, now, now, now),
                    )

            seen_variant_ids: set[str] = set()
            for row in variants:
                variant_id = str(row["variant_id"])
                skill_id = str(row["skill_id"])
                seen_variant_ids.add(variant_id)
                source_tuple = (
                    str(row.get("source_class", "")),
                    str(row.get("root", "")),
                    int(row.get("authority_tier", 0)),
                    bool(row.get("selectable", False)),
                )
                source_id = source_ids[source_tuple]
                values = (
                    skill_id,
                    source_id,
                    str(row.get("path", "")),
                    str(row.get("root", "")),
                    str(row.get("sha256", "")),
                    int(row.get("size", 0)),
                    int(row.get("authority_tier", 0)),
                    int(bool(row.get("selectable", False))),
                    int(row.get("priority", row.get("authority_tier", 0))),
                    int(bool(row.get("category_router", False))),
                )
                existing = conn.execute(
                    "SELECT * FROM skill_variants WHERE variant_id=?", (variant_id,)
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO skill_variants(
                            variant_id, skill_id, source_id, path, root, sha256, size,
                            authority_tier, selectable, priority, category_router,
                            active, last_seen_run, created_at, updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)
                        """,
                        (variant_id, *values, run_id, now, now),
                    )
                    counts["variants"]["added"] += 1
                else:
                    current = (
                        existing["skill_id"],
                        int(existing["source_id"]),
                        existing["path"],
                        existing["root"],
                        existing["sha256"],
                        int(existing["size"]),
                        int(existing["authority_tier"]),
                        int(existing["selectable"]),
                        int(existing["priority"]),
                        int(existing["category_router"]),
                    )
                    if current == values and int(existing["active"]) == 1:
                        counts["variants"]["unchanged"] += 1
                    else:
                        counts["variants"]["updated"] += 1
                    conn.execute(
                        """
                        UPDATE skill_variants SET skill_id=?, source_id=?, path=?, root=?,
                            sha256=?, size=?, authority_tier=?, selectable=?, priority=?,
                            category_router=?, active=1, last_seen_run=?, updated_at=?
                        WHERE variant_id=?
                        """,
                        (*values, run_id, now, variant_id),
                    )

            counts["sources"]["stale"] = len(old_active_sources - seen_source_keys)
            counts["skills"]["stale"] = len(old_active_skills - set(selected))
            counts["variants"]["stale"] = len(old_active_variants - seen_variant_ids)
            for source_key in sorted(old_active_sources - seen_source_keys):
                conn.execute(
                    "UPDATE sources SET active=0, updated_at=? WHERE source_key=?",
                    (now, source_key),
                )
            for skill_id in sorted(old_active_skills - set(selected)):
                conn.execute(
                    "UPDATE skills SET active=0, updated_at=? WHERE skill_id=?",
                    (now, skill_id),
                )
            for variant_id in sorted(old_active_variants - seen_variant_ids):
                conn.execute(
                    "UPDATE skill_variants SET active=0, updated_at=? WHERE variant_id=?",
                    (now, variant_id),
                )
            self.db.audit(
                conn,
                "registry.reconcile",
                "registry",
                run_id,
                {
                    "counts": counts,
                    "snapshot_skill_count": len(selected),
                    "snapshot_variant_count": len(variants),
                },
            )

        return {
            "run_id": run_id,
            "counts": counts,
            "snapshot": {
                "skill_count": len(selected),
                "variant_count": len(variants),
                "nonselectable_variant_count": sum(
                    1 for row in variants if not bool(row.get("selectable", False))
                ),
            },
            "compatibility": compatibility,
        }

    def parity(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        selected = self._selected_by_id(snapshot)
        variants = self._variants(snapshot)
        db_skills = {
            row["skill_id"]: row
            for row in self.db.connection.execute(
                "SELECT * FROM skills WHERE active=1 ORDER BY skill_id"
            )
        }
        db_variants = {
            row["variant_id"]: row
            for row in self.db.connection.execute(
                "SELECT * FROM skill_variants WHERE active=1 ORDER BY variant_id"
            )
        }
        selected_mismatches: list[str] = []
        for skill_id, row in selected.items():
            db_row = db_skills.get(skill_id)
            if db_row is None or db_row["selected_variant_id"] != row.get("variant_id"):
                selected_mismatches.append(skill_id)
        variant_mismatches: list[str] = []
        for row in variants:
            db_row = db_variants.get(str(row["variant_id"]))
            if db_row is None:
                variant_mismatches.append(str(row["variant_id"]))
                continue
            if (
                db_row["path"] != str(row.get("path", ""))
                or db_row["sha256"] != str(row.get("sha256", ""))
                or int(db_row["authority_tier"]) != int(row.get("authority_tier", 0))
                or bool(db_row["selectable"]) != bool(row.get("selectable", False))
            ):
                variant_mismatches.append(str(row["variant_id"]))
        return {
            "ok": (
                len(db_skills) == len(selected)
                and len(db_variants) == len(variants)
                and not selected_mismatches
                and not variant_mismatches
            ),
            "snapshot_skill_count": len(selected),
            "db_skill_count": len(db_skills),
            "snapshot_variant_count": len(variants),
            "db_variant_count": len(db_variants),
            "selected_mismatches": selected_mismatches,
            "variant_mismatches": variant_mismatches,
            "db_nonselectable_variant_count": sum(
                1 for row in db_variants.values() if not bool(row["selectable"])
            ),
        }
