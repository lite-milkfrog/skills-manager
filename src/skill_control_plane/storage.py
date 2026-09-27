from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ControlPlaneDB:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser().absolute()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> ControlPlaneDB:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        if self.connection.in_transaction:
            raise RuntimeError("nested-transactions-not-supported")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def migrate(self) -> int:
        with self.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                int(row["version"]) for row in conn.execute("SELECT version FROM schema_migrations")
            }
            if 1 not in applied:
                self._migration_001(conn)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(1, ?, ?)",
                    ("management-workflow-run-core", utc_now()),
                )
            if 2 not in applied:
                self._migration_002(conn)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(2, ?, ?)",
                    ("variant-path-history", utc_now()),
                )
            if 3 not in applied:
                self._migration_003(conn)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(3, ?, ?)",
                    ("durable-deployment-transactions", utc_now()),
                )
            if 4 not in applied:
                self._migration_004(conn)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(4, ?, ?)",
                    ("semantic-workflow-stages", utc_now()),
                )
        return self.schema_version()

    def schema_version(self) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
        return int(row["version"]) if row else 0

    def _migration_001(self, conn: sqlite3.Connection) -> None:
        script = """
            CREATE TABLE sources (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL UNIQUE,
                source_class TEXT NOT NULL,
                path TEXT NOT NULL,
                authority_tier INTEGER NOT NULL,
                selectable INTEGER NOT NULL CHECK(selectable IN (0,1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                last_seen_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_class, path, authority_tier, selectable)
            );

            CREATE TABLE skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                selected_variant_id TEXT,
                category_router INTEGER NOT NULL DEFAULT 0 CHECK(category_router IN (0,1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE skill_variants (
                variant_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
                path TEXT NOT NULL,
                root TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                authority_tier INTEGER NOT NULL,
                selectable INTEGER NOT NULL CHECK(selectable IN (0,1)),
                priority INTEGER NOT NULL,
                category_router INTEGER NOT NULL DEFAULT 0 CHECK(category_router IN (0,1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                last_seen_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX one_active_selected_identity
            ON skills(skill_id) WHERE active = 1;

            CREATE TABLE categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE skill_categories (
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                category_id TEXT NOT NULL REFERENCES categories(category_id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                PRIMARY KEY(skill_id, category_id)
            );

            CREATE TABLE tags (
                tag_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE skill_tags (
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                tag_id TEXT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                PRIMARY KEY(skill_id, tag_id)
            );

            CREATE TABLE presets (
                preset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE preset_skills (
                preset_id TEXT NOT NULL REFERENCES presets(preset_id) ON DELETE CASCADE,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                ordinal INTEGER NOT NULL DEFAULT 0,
                required INTEGER NOT NULL DEFAULT 1 CHECK(required IN (0,1)),
                created_at TEXT NOT NULL,
                PRIMARY KEY(preset_id, skill_id)
            );

            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                root_path TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                workspace_id TEXT REFERENCES workspaces(workspace_id) ON DELETE SET NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE deployments (
                deployment_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                workspace_id TEXT REFERENCES workspaces(workspace_id) ON DELETE SET NULL,
                agent_id TEXT REFERENCES agents(agent_id) ON DELETE SET NULL,
                intent TEXT NOT NULL,
                state TEXT NOT NULL,
                target_path TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE workflows (
                workflow_id TEXT PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE,
                version INTEGER NOT NULL CHECK(version >= 1),
                description TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(name, version)
            );

            CREATE TABLE workflow_stages (
                stage_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
                stage_key TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                condition_json TEXT NOT NULL DEFAULT '{}',
                success_gate_json TEXT NOT NULL DEFAULT '{}',
                failure_gate_json TEXT NOT NULL DEFAULT '{}',
                retry_limit INTEGER NOT NULL DEFAULT 0 CHECK(retry_limit >= 0),
                loop_limit INTEGER NOT NULL DEFAULT 0 CHECK(loop_limit >= 0),
                loop_stop_condition_json TEXT NOT NULL DEFAULT '{}',
                fallback_stage_id TEXT REFERENCES workflow_stages(stage_id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(workflow_id, stage_key),
                UNIQUE(workflow_id, ordinal)
            );

            CREATE TABLE workflow_skill_bindings (
                binding_id TEXT PRIMARY KEY,
                stage_id TEXT NOT NULL REFERENCES workflow_stages(stage_id) ON DELETE CASCADE,
                binding_key TEXT NOT NULL,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                binding_type TEXT NOT NULL
                    CHECK(binding_type IN ('required','optional','conditional')),
                condition_json TEXT NOT NULL DEFAULT '{}',
                fallback_skill_id TEXT REFERENCES skills(skill_id) ON DELETE RESTRICT,
                ordinal INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(stage_id, binding_key),
                UNIQUE(stage_id, ordinal)
            );

            CREATE TABLE workflow_runs (
                run_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE RESTRICT,
                status TEXT NOT NULL
                    CHECK(
                        status IN ('planned','active','blocked','completed','failed','cancelled')
                    ),
                current_stage_id TEXT REFERENCES workflow_stages(stage_id) ON DELETE RESTRICT,
                context_json TEXT NOT NULL DEFAULT '{}',
                terminal_result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE workflow_run_stages (
                run_stage_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
                stage_id TEXT NOT NULL REFERENCES workflow_stages(stage_id) ON DELETE RESTRICT,
                ordinal INTEGER NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('pending','running','blocked','succeeded','failed','skipped')),
                resolved_bindings_json TEXT NOT NULL DEFAULT '[]',
                retry_count INTEGER NOT NULL DEFAULT 0 CHECK(retry_count >= 0),
                loop_count INTEGER NOT NULL DEFAULT 0 CHECK(loop_count >= 0),
                gate_result_json TEXT,
                blocked_reason TEXT,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, stage_id)
            );

            CREATE TABLE workflow_evidence (
                evidence_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
                run_stage_id TEXT NOT NULL
                    REFERENCES workflow_run_stages(run_stage_id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX idx_variants_skill ON skill_variants(skill_id, active);
            CREATE INDEX idx_variants_path ON skill_variants(path, active);
            CREATE INDEX idx_variants_source ON skill_variants(source_id, active);
            CREATE INDEX idx_deployments_skill ON deployments(skill_id);
            CREATE INDEX idx_workflow_stages_workflow ON workflow_stages(workflow_id, ordinal);
            CREATE INDEX idx_run_stages_run ON workflow_run_stages(run_id, ordinal);
            CREATE INDEX idx_evidence_stage ON workflow_evidence(run_stage_id, created_at);
            """
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)

    def _migration_002(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='skill_variants'"
        ).fetchone()
        if row is None:
            raise RuntimeError("skill-variants-table-missing")
        table_sql = str(row["sql"] or "").upper()
        if "PATH TEXT NOT NULL UNIQUE" not in table_sql:
            return

        conn.execute("ALTER TABLE skill_variants RENAME TO skill_variants_v1")
        conn.execute(
            """
            CREATE TABLE skill_variants (
                variant_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
                path TEXT NOT NULL,
                root TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                authority_tier INTEGER NOT NULL,
                selectable INTEGER NOT NULL CHECK(selectable IN (0,1)),
                priority INTEGER NOT NULL,
                category_router INTEGER NOT NULL DEFAULT 0 CHECK(category_router IN (0,1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                last_seen_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO skill_variants(
                variant_id,skill_id,source_id,path,root,sha256,size,authority_tier,
                selectable,priority,category_router,active,last_seen_run,created_at,updated_at
            )
            SELECT
                variant_id,skill_id,source_id,path,root,sha256,size,authority_tier,
                selectable,priority,category_router,active,last_seen_run,created_at,updated_at
            FROM skill_variants_v1
            """
        )
        conn.execute("DROP TABLE skill_variants_v1")
        conn.execute("CREATE INDEX idx_variants_skill ON skill_variants(skill_id, active)")
        conn.execute("CREATE INDEX idx_variants_path ON skill_variants(path, active)")
        conn.execute("CREATE INDEX idx_variants_source ON skill_variants(source_id, active)")

    def _migration_003(self, conn: sqlite3.Connection) -> None:
        statements = [
            """
            CREATE TABLE deployment_transactions (
                transaction_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                operation TEXT NOT NULL CHECK(
                    operation IN (
                        'adopt_existing',
                        'deploy_from_local_source',
                        'update_managed',
                        'relocate_managed',
                        'undeploy_to_quarantine'
                    )
                ),
                source_path TEXT,
                source_key TEXT,
                target_path TEXT,
                target_key TEXT,
                source_digest TEXT,
                target_digest TEXT,
                ownership_class TEXT NOT NULL,
                preconditions_json TEXT NOT NULL DEFAULT '{}',
                state TEXT NOT NULL CHECK(
                    state IN (
                        'planned',
                        'validated',
                        'applying',
                        'verifying',
                        'committed',
                        'recovery_required',
                        'rolling_back',
                        'rolled_back'
                    )
                ),
                rollback_state TEXT NOT NULL DEFAULT 'none',
                evidence_json TEXT NOT NULL DEFAULT '{}',
                error_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE deployment_steps (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL
                    REFERENCES deployment_transactions(transaction_id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                state TEXT NOT NULL CHECK(
                    state IN ('pending','applied','verified','rolled_back','skipped')
                ),
                evidence_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(transaction_id, ordinal),
                UNIQUE(transaction_id, step_name)
            )
            """,
            """
            CREATE TABLE managed_paths (
                path_key TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                skill_id TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
                ownership_class TEXT NOT NULL CHECK(
                    ownership_class IN ('control_plane_owned','explicitly_adopted_external')
                ),
                content_digest TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                origin_transaction_id TEXT
                    REFERENCES deployment_transactions(transaction_id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX uq_active_deployment_skill
            ON deployment_transactions(skill_id)
            WHERE state IN (
                'planned','validated','applying','verifying',
                'recovery_required','rolling_back'
            )
            """,
            """
            CREATE UNIQUE INDEX uq_active_deployment_target
            ON deployment_transactions(target_key)
            WHERE target_key IS NOT NULL AND state IN (
                'planned','validated','applying','verifying',
                'recovery_required','rolling_back'
            )
            """,
            """
            CREATE INDEX idx_deployment_transactions_state
            ON deployment_transactions(state, updated_at)
            """,
            """
            CREATE INDEX idx_deployment_steps_transaction
            ON deployment_steps(transaction_id, ordinal)
            """,
            """
            CREATE INDEX idx_managed_paths_skill
            ON managed_paths(skill_id, active)
            """,
        ]
        for statement in statements:
            conn.execute(statement.strip())

    def _migration_004(self, conn: sqlite3.Connection) -> None:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workflow_stages'"
        ).fetchone()
        if table is None:
            return
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(workflow_stages)").fetchall()
        }
        additions = [
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("instructions", "TEXT NOT NULL DEFAULT ''"),
            ("expected_output", "TEXT NOT NULL DEFAULT ''"),
            ("completion_criteria", "TEXT NOT NULL DEFAULT ''"),
        ]
        for name, definition in additions:
            if name not in columns:
                conn.execute(f"ALTER TABLE workflow_stages ADD COLUMN {name} {definition}")

    def integrity(self) -> dict[str, Any]:
        integrity = [row[0] for row in self.connection.execute("PRAGMA integrity_check").fetchall()]
        foreign_keys = [
            tuple(row) for row in self.connection.execute("PRAGMA foreign_key_check").fetchall()
        ]
        return {
            "integrity_check": integrity,
            "foreign_key_violations": foreign_keys,
            "schema_version": self.schema_version(),
        }

    def audit(
        self,
        conn: sqlite3.Connection,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log(action, entity_type, entity_id, payload_json, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                entity_id,
                json.dumps(payload or {}, sort_keys=True, ensure_ascii=False),
                utc_now(),
            ),
        )
