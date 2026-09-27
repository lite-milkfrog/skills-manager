from __future__ import annotations

from typing import Any

from .storage import ControlPlaneDB, utc_now
from .utils import json_text, json_value, stable_id


class ValidationError(ValueError):
    pass


class ManagementService:
    def __init__(self, db: ControlPlaneDB) -> None:
        self.db = db
        self.db.migrate()

    def _require_skill(self, conn, skill_id: str) -> None:
        row = conn.execute(
            "SELECT skill_id FROM skills WHERE skill_id=? AND active=1", (skill_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-skill-id:{skill_id}")

    def _plan(
        self, action: str, entity_type: str, entity_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "dry_run": True,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "values": values,
        }

    def upsert_category(
        self, name: str, description: str = "", *, dry_run: bool = False
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValidationError("category-name-required")
        category_id = stable_id("cat", name)
        values = {"name": name, "description": description}
        if dry_run:
            return self._plan("category.upsert", "category", category_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO categories(category_id,name,description,created_at,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(category_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    updated_at=excluded.updated_at
                """,
                (category_id, name, description, now, now),
            )
            self.db.audit(conn, "category.upsert", "category", category_id, values)
        return {"category_id": category_id, **values}

    def get_category(self, category_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM categories WHERE category_id=?", (category_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-category-id:{category_id}")
        return {
            "category_id": category_id,
            "name": row["name"],
            "description": row["description"],
        }

    def delete_category(self, category_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            exists = self.db.connection.execute(
                "SELECT category_id FROM categories WHERE category_id=?", (category_id,)
            ).fetchone()
            if exists is None:
                raise ValidationError(f"unknown-category-id:{category_id}")
            return self._plan("category.delete", "category", category_id, {})
        with self.db.transaction() as conn:
            exists = conn.execute(
                "SELECT category_id FROM categories WHERE category_id=?", (category_id,)
            ).fetchone()
            if exists is None:
                raise ValidationError(f"unknown-category-id:{category_id}")
            conn.execute("DELETE FROM categories WHERE category_id=?", (category_id,))
            self.db.audit(conn, "category.delete", "category", category_id, {})
        return {"deleted": category_id}

    def upsert_tag(self, name: str, *, dry_run: bool = False) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValidationError("tag-name-required")
        tag_id = stable_id("tag", name)
        values = {"name": name}
        if dry_run:
            return self._plan("tag.upsert", "tag", tag_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tags(tag_id,name,created_at,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(tag_id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at
                """,
                (tag_id, name, now, now),
            )
            self.db.audit(conn, "tag.upsert", "tag", tag_id, values)
        return {"tag_id": tag_id, **values}

    def get_tag(self, tag_id: str) -> dict[str, Any]:
        row = self.db.connection.execute("SELECT * FROM tags WHERE tag_id=?", (tag_id,)).fetchone()
        if row is None:
            raise ValidationError(f"unknown-tag-id:{tag_id}")
        return {"tag_id": tag_id, "name": row["name"]}

    def list_sources(self) -> list[dict[str, Any]]:
        return [
            {
                "source_key": row["source_key"],
                "source_class": row["source_class"],
                "path": row["path"],
                "authority_tier": int(row["authority_tier"]),
                "selectable": bool(row["selectable"]),
                "active": bool(row["active"]),
            }
            for row in self.db.connection.execute(
                """
                SELECT source_key,source_class,path,authority_tier,selectable,active
                FROM sources
                ORDER BY active DESC, authority_tier DESC, path, source_key
                """
            )
        ]

    def delete_tag(self, tag_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            exists = self.db.connection.execute(
                "SELECT tag_id FROM tags WHERE tag_id=?", (tag_id,)
            ).fetchone()
            if exists is None:
                raise ValidationError(f"unknown-tag-id:{tag_id}")
            return self._plan("tag.delete", "tag", tag_id, {})
        with self.db.transaction() as conn:
            exists = conn.execute("SELECT tag_id FROM tags WHERE tag_id=?", (tag_id,)).fetchone()
            if exists is None:
                raise ValidationError(f"unknown-tag-id:{tag_id}")
            conn.execute("DELETE FROM tags WHERE tag_id=?", (tag_id,))
            self.db.audit(conn, "tag.delete", "tag", tag_id, {})
        return {"deleted": tag_id}

    def bind_category(
        self, skill_id: str, category_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        values = {"skill_id": skill_id, "category_id": category_id}
        if dry_run:
            self._require_skill(self.db.connection, skill_id)
            if (
                self.db.connection.execute(
                    "SELECT 1 FROM categories WHERE category_id=?", (category_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-category-id:{category_id}")
            return self._plan("skill.category.bind", "skill", skill_id, values)
        with self.db.transaction() as conn:
            self._require_skill(conn, skill_id)
            if (
                conn.execute(
                    "SELECT 1 FROM categories WHERE category_id=?", (category_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-category-id:{category_id}")
            conn.execute(
                """
                INSERT OR IGNORE INTO skill_categories(
                    skill_id,category_id,created_at
                ) VALUES(?,?,?)
                """,
                (skill_id, category_id, utc_now()),
            )
            self.db.audit(conn, "skill.category.bind", "skill", skill_id, values)
        return values

    def bind_tag(self, skill_id: str, tag_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        values = {"skill_id": skill_id, "tag_id": tag_id}
        if dry_run:
            self._require_skill(self.db.connection, skill_id)
            if (
                self.db.connection.execute(
                    "SELECT 1 FROM tags WHERE tag_id=?", (tag_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-tag-id:{tag_id}")
            return self._plan("skill.tag.bind", "skill", skill_id, values)
        with self.db.transaction() as conn:
            self._require_skill(conn, skill_id)
            if conn.execute("SELECT 1 FROM tags WHERE tag_id=?", (tag_id,)).fetchone() is None:
                raise ValidationError(f"unknown-tag-id:{tag_id}")
            conn.execute(
                "INSERT OR IGNORE INTO skill_tags(skill_id,tag_id,created_at) VALUES(?,?,?)",
                (skill_id, tag_id, utc_now()),
            )
            self.db.audit(conn, "skill.tag.bind", "skill", skill_id, values)
        return values

    def list_categories(self) -> list[dict[str, Any]]:
        return [
            {
                "category_id": row["category_id"],
                "name": row["name"],
                "description": row["description"],
            }
            for row in self.db.connection.execute(
                "SELECT category_id,name,description FROM categories ORDER BY name,category_id"
            )
        ]

    def list_tags(self) -> list[dict[str, Any]]:
        return [
            {"tag_id": row["tag_id"], "name": row["name"]}
            for row in self.db.connection.execute(
                "SELECT tag_id,name FROM tags ORDER BY name,tag_id"
            )
        ]

    def get_skill_organization(self, skill_id: str) -> dict[str, Any]:
        self._require_skill(self.db.connection, skill_id)
        categories = [
            {
                "category_id": row["category_id"],
                "name": row["name"],
                "description": row["description"],
            }
            for row in self.db.connection.execute(
                """
                SELECT c.category_id,c.name,c.description
                FROM categories c
                JOIN skill_categories sc ON sc.category_id=c.category_id
                WHERE sc.skill_id=?
                ORDER BY c.name,c.category_id
                """,
                (skill_id,),
            )
        ]
        tags = [
            {"tag_id": row["tag_id"], "name": row["name"]}
            for row in self.db.connection.execute(
                """
                SELECT t.tag_id,t.name
                FROM tags t
                JOIN skill_tags st ON st.tag_id=t.tag_id
                WHERE st.skill_id=?
                ORDER BY t.name,t.tag_id
                """,
                (skill_id,),
            )
        ]
        return {"skill_id": skill_id, "categories": categories, "tags": tags}

    def unbind_category(
        self, skill_id: str, category_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        values = {"skill_id": skill_id, "category_id": category_id}
        self._require_skill(self.db.connection, skill_id)
        if (
            self.db.connection.execute(
                "SELECT 1 FROM categories WHERE category_id=?", (category_id,)
            ).fetchone()
            is None
        ):
            raise ValidationError(f"unknown-category-id:{category_id}")
        if dry_run:
            return self._plan("skill.category.unbind", "skill", skill_id, values)
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM skill_categories WHERE skill_id=? AND category_id=?",
                (skill_id, category_id),
            )
            self.db.audit(conn, "skill.category.unbind", "skill", skill_id, values)
        return values

    def unbind_tag(
        self, skill_id: str, tag_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        values = {"skill_id": skill_id, "tag_id": tag_id}
        self._require_skill(self.db.connection, skill_id)
        if (
            self.db.connection.execute("SELECT 1 FROM tags WHERE tag_id=?", (tag_id,)).fetchone()
            is None
        ):
            raise ValidationError(f"unknown-tag-id:{tag_id}")
        if dry_run:
            return self._plan("skill.tag.unbind", "skill", skill_id, values)
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM skill_tags WHERE skill_id=? AND tag_id=?",
                (skill_id, tag_id),
            )
            self.db.audit(conn, "skill.tag.unbind", "skill", skill_id, values)
        return values


    def upsert_preset(
        self,
        name: str,
        skill_ids: list[str],
        description: str = "",
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValidationError("preset-name-required")
        preset_id = stable_id("preset", name)
        values = {"name": name, "description": description, "skill_ids": list(skill_ids)}
        if dry_run:
            for skill_id in skill_ids:
                self._require_skill(self.db.connection, skill_id)
            return self._plan("preset.upsert", "preset", preset_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            for skill_id in skill_ids:
                self._require_skill(conn, skill_id)
            conn.execute(
                """
                INSERT INTO presets(preset_id,name,description,created_at,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(preset_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    updated_at=excluded.updated_at
                """,
                (preset_id, name, description, now, now),
            )
            conn.execute("DELETE FROM preset_skills WHERE preset_id=?", (preset_id,))
            for ordinal, skill_id in enumerate(skill_ids):
                conn.execute(
                    """
                    INSERT INTO preset_skills(preset_id,skill_id,ordinal,required,created_at)
                    VALUES(?,?,?,?,?)
                    """,
                    (preset_id, skill_id, ordinal, 1, now),
                )
            self.db.audit(conn, "preset.upsert", "preset", preset_id, values)
        return {"preset_id": preset_id, **values}

    def get_preset(self, preset_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM presets WHERE preset_id=?", (preset_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-preset-id:{preset_id}")
        skill_ids = [
            item["skill_id"]
            for item in self.db.connection.execute(
                "SELECT skill_id FROM preset_skills WHERE preset_id=? ORDER BY ordinal,skill_id",
                (preset_id,),
            )
        ]
        return {
            "preset_id": preset_id,
            "name": row["name"],
            "description": row["description"],
            "skill_ids": skill_ids,
        }

    def upsert_workspace(
        self,
        name: str,
        root_path: str,
        metadata: dict[str, Any] | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        workspace_id = stable_id("ws", name)
        values = {"name": name, "root_path": root_path, "metadata": metadata or {}}
        if dry_run:
            return self._plan("workspace.upsert", "workspace", workspace_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workspaces(
                    workspace_id,name,root_path,metadata_json,created_at,updated_at
                )
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    name=excluded.name, root_path=excluded.root_path,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (workspace_id, name, root_path, json_text(metadata or {}), now, now),
            )
            self.db.audit(conn, "workspace.upsert", "workspace", workspace_id, values)
        return {"workspace_id": workspace_id, **values}

    def upsert_agent(
        self,
        name: str,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        agent_id = stable_id("agent", name)
        values = {"name": name, "workspace_id": workspace_id, "metadata": metadata or {}}
        if dry_run:
            if (
                workspace_id
                and self.db.connection.execute(
                    "SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-workspace-id:{workspace_id}")
            return self._plan("agent.upsert", "agent", agent_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            if (
                workspace_id
                and conn.execute(
                    "SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-workspace-id:{workspace_id}")
            conn.execute(
                """
                INSERT INTO agents(agent_id,name,workspace_id,metadata_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    name=excluded.name, workspace_id=excluded.workspace_id,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (agent_id, name, workspace_id, json_text(metadata or {}), now, now),
            )
            self.db.audit(conn, "agent.upsert", "agent", agent_id, values)
        return {"agent_id": agent_id, **values}

    def upsert_deployment(
        self,
        skill_id: str,
        intent: str,
        state: str,
        *,
        workspace_id: str | None = None,
        agent_id: str | None = None,
        target_path: str | None = None,
        metadata: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        deployment_id = stable_id(
            "deploy", skill_id, workspace_id or "", agent_id or "", target_path or ""
        )
        values = {
            "skill_id": skill_id,
            "intent": intent,
            "state": state,
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "target_path": target_path,
            "metadata": metadata or {},
        }
        if dry_run:
            self._require_skill(self.db.connection, skill_id)
            if (
                workspace_id
                and self.db.connection.execute(
                    "SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-workspace-id:{workspace_id}")
            if (
                agent_id
                and self.db.connection.execute(
                    "SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-agent-id:{agent_id}")
            return self._plan("deployment.upsert", "deployment", deployment_id, values)
        now = utc_now()
        with self.db.transaction() as conn:
            self._require_skill(conn, skill_id)
            if (
                workspace_id
                and conn.execute(
                    "SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)
                ).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-workspace-id:{workspace_id}")
            if (
                agent_id
                and conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
                is None
            ):
                raise ValidationError(f"unknown-agent-id:{agent_id}")
            conn.execute(
                """
                INSERT INTO deployments(
                    deployment_id,skill_id,workspace_id,agent_id,intent,state,target_path,
                    metadata_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(deployment_id) DO UPDATE SET
                    intent=excluded.intent, state=excluded.state,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (
                    deployment_id,
                    skill_id,
                    workspace_id,
                    agent_id,
                    intent,
                    state,
                    target_path,
                    json_text(metadata or {}),
                    now,
                    now,
                ),
            )
            self.db.audit(conn, "deployment.upsert", "deployment", deployment_id, values)
        return {"deployment_id": deployment_id, **values}

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM workspaces WHERE workspace_id=?", (workspace_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-workspace-id:{workspace_id}")
        return {
            "workspace_id": workspace_id,
            "name": row["name"],
            "root_path": row["root_path"],
            "metadata": json_value(row["metadata_json"], {}),
        }

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-agent-id:{agent_id}")
        return {
            "agent_id": agent_id,
            "name": row["name"],
            "workspace_id": row["workspace_id"],
            "metadata": json_value(row["metadata_json"], {}),
        }

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM deployments WHERE deployment_id=?", (deployment_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"unknown-deployment-id:{deployment_id}")
        return {
            "deployment_id": deployment_id,
            "skill_id": row["skill_id"],
            "workspace_id": row["workspace_id"],
            "agent_id": row["agent_id"],
            "intent": row["intent"],
            "state": row["state"],
            "target_path": row["target_path"],
            "metadata": json_value(row["metadata_json"], {}),
        }

    def list_workspaces(self) -> list[dict[str, Any]]:
        return [
            {
                "workspace_id": row["workspace_id"],
                "name": row["name"],
                "root_path": row["root_path"],
                "metadata": json_value(row["metadata_json"], {}),
            }
            for row in self.db.connection.execute(
                "SELECT * FROM workspaces ORDER BY name,workspace_id"
            )
        ]

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": row["agent_id"],
                "name": row["name"],
                "workspace_id": row["workspace_id"],
                "metadata": json_value(row["metadata_json"], {}),
            }
            for row in self.db.connection.execute(
                "SELECT * FROM agents ORDER BY name,agent_id"
            )
        ]


    def audit_count(self) -> int:
        row = self.db.connection.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()
        return int(row["n"])
