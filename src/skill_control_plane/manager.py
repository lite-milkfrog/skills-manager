from __future__ import annotations

import re
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .core import Registry, validate_skill_file
from .deployment import DeploymentService
from .management import ManagementService, ValidationError
from .registry_store import RegistryStore
from .run_state import RunService
from .search_terms import normalized_search_terms
from .storage import ControlPlaneDB
from .utils import json_value
from .workflow import WorkflowService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANAGED_ROOT = PROJECT_ROOT / "runtime" / "m04-managed"
DEFAULT_PROTECTED_ROOTS = (
    PROJECT_ROOT / ".." / "webgpt-as-codex",
    PROJECT_ROOT / ".." / ".skills",
)

_SKILL_RESOURCE_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".ps1",
    ".cmd",
    ".bat",
    ".sh",
}
_SKILL_RESOURCE_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
}
_SKILL_RESOURCE_MAX_FILES = 64
_SKILL_RESOURCE_MAX_FILE_BYTES = 256 * 1024
_SKILL_RESOURCE_MAX_TOTAL_BYTES = 1024 * 1024
_SKILL_RESOLVE_DEFAULT_DEPTH = 2
_SKILL_RESOLVE_MAX_DEPTH = 4
_SKILL_RESOLVE_DEFAULT_SKILLS = 12
_SKILL_RESOLVE_MAX_SKILLS = 24
_SKILL_RESOLVE_DEFAULT_BYTES = 512 * 1024
_SKILL_RESOLVE_MAX_BYTES = 2 * 1024 * 1024

_RESOURCE_REFERENCE_RE = re.compile(
    r"(?:\./)?((?:[a-z0-9._-]+/)*[a-z0-9._-]+\.(?:md|txt|json|ya?ml|py|m?js|cjs|tsx?|jsx|ps1|cmd|bat|sh))",
    re.IGNORECASE,
)
_SKILL_TOKEN_RE = re.compile(
    r"(?<![a-z0-9._-])([a-z][a-z0-9._-]{2,})(?![a-z0-9._-])", re.IGNORECASE
)
_CHILD_SKILL_PATTERNS = (
    re.compile(r"`([a-z0-9][a-z0-9._-]{1,})`\s*(?:skill|技能)", re.IGNORECASE),
    re.compile(
        r"(?:skill(?:_id)?|子\s*skill|子技能)\s*[:=：]\s*`?([a-z0-9][a-z0-9._-]{1,})`?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:route through|route to|delegate to|路由到|交给)\s+`?([a-z][a-z0-9._-]{2,})`?",
        re.IGNORECASE,
    ),
)


class ManagerError(RuntimeError):
    pass


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _skill_resource_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".md":
        return "markdown"
    if suffix in {".json", ".yaml", ".yml"}:
        return "data"
    if suffix in {
        ".py",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".jsx",
        ".ps1",
        ".cmd",
        ".bat",
        ".sh",
    }:
        return "script"
    return "text"


def _normalize_resource_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def _referenced_resource_paths(content: str) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for match in _RESOURCE_REFERENCE_RE.finditer(content or ""):
        value = _normalize_resource_path(str(match.group(1) or ""))
        if not value or "../" in value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(value)
    return paths


def _capability_kind(skill: dict[str, Any], content: str) -> str:
    text = "\\n".join(
        str(value)
        for value in (
            skill.get("name"),
            skill.get("skill_id"),
            skill.get("description"),
            content,
        )
        if value
    ).casefold()
    if bool(skill.get("category_router")) or "references/routes.md" in text:
        return "router"
    has_tool_protocol = bool(
        re.search(
            r"\bmcp\b|playwright|serena|coding tools|windows-mcp|desktop commander|gateway",
            text,
        )
    )
    has_agent_protocol = bool(
        re.search(
            r"\bagent\b|tool routing|recovery|fallback|validation|执行协议|工具路由|恢复", text
        )
    )
    if has_tool_protocol and has_agent_protocol:
        return "agent"
    if re.search(r"\brouter\b|route selection|routing skill|内部路由|路由技能", text):
        return "router"
    if re.search(
        r"default workflow|workflow|orchestrat|pipeline|multi-step|工作流|执行流程|多步流程", text
    ):
        return "composite"
    if re.search(
        r"other skills|child skill|route.+skill|use.+skill|call.+skill|"
        r"调用.{0,20}skill|使用.{0,20}skill",
        text,
    ):
        return "composite"
    return "single"


def _route_like_resource(path: str) -> bool:
    normalized = _normalize_resource_path(path).casefold()
    return bool(
        re.search(
            r"(?:^|/)(?:routing\.md|routes\.md|route\.md|references/routes\.md|routes/[^/]+/skill\.md)$",
            normalized,
        )
    )


def _task_relevance_terms(task: str) -> list[str]:
    terms = [term.casefold() for term in normalized_search_terms(task) if term.strip()]
    for chunk in re.findall(r"[\u3400-\u9fff]+", task):
        for width in (4, 3, 2):
            if len(chunk) < width:
                continue
            terms.extend(
                chunk[index : index + width].casefold()
                for index in range(0, len(chunk) - width + 1)
            )
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


class ManagerBackend:
    def __init__(
        self,
        registry: Registry,
        db_path: Path | str,
        *,
        explorer_opener: Callable[[Path], None] | None = None,
    ) -> None:
        self.registry = registry
        self.db_path = Path(db_path).expanduser().absolute()
        self.explorer_opener = explorer_opener

    def _db(self) -> ControlPlaneDB:
        db = ControlPlaneDB(self.db_path)
        db.migrate()
        return db

    @staticmethod
    def _page(items: list[dict[str, Any]], cursor: int = 0, limit: int = 50) -> dict[str, Any]:
        offset = max(0, int(cursor))
        size = max(1, min(int(limit), 200))
        rows = items[offset : offset + size]
        next_cursor = offset + len(rows)
        return {
            "items": rows,
            "total": len(items),
            "cursor": offset,
            "next_cursor": next_cursor if next_cursor < len(items) else None,
        }

    def overview(self) -> dict[str, Any]:
        with self._db() as db:
            counts = {
                "workflows": int(
                    db.connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
                ),
                "runs": int(
                    db.connection.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
                ),
                "categories": int(
                    db.connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
                ),
                "tags": int(db.connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0]),
                "audit": int(db.connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]),
            }
        return {
            "health": self.runtime_health(),
            "inventory": self.registry.status(),
            "counts": counts,
            "recent_runs": self.run_list(limit=6)["items"],
            "recent_workflows": self.workflow_list(limit=6)["items"],
        }

    def skill_facets(self) -> dict[str, Any]:
        sources: dict[str, int] = {}
        tiers: dict[int, int] = {}
        for row in self.registry.records():
            source = str(row.get("source_class", "unknown"))
            sources[source] = sources.get(source, 0) + 1
            tier = int(row.get("authority_tier", 0))
            tiers[tier] = tiers.get(tier, 0) + 1
        return {
            "source_classes": [
                {"value": k, "count": v}
                for k, v in sorted(sources.items(), key=lambda item: (-item[1], item[0]))
            ],
            "authority_tiers": [
                {"value": k, "count": v} for k, v in sorted(tiers.items(), reverse=True)
            ],
        }

    def _organization_map(self, skill_ids: list[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        result = {skill_id: {"categories": [], "tags": []} for skill_id in skill_ids}
        if not skill_ids:
            return result
        placeholders = ",".join("?" for _ in skill_ids)
        with self._db() as db:
            for row in db.connection.execute(
                f"""
                SELECT sc.skill_id,c.category_id,c.name
                FROM skill_categories sc
                JOIN categories c ON c.category_id=sc.category_id
                WHERE sc.skill_id IN ({placeholders})
                ORDER BY c.name,c.category_id
                """,
                skill_ids,
            ):
                result[str(row["skill_id"])]["categories"].append(
                    {"category_id": row["category_id"], "name": row["name"]}
                )
            for row in db.connection.execute(
                f"""
                SELECT st.skill_id,t.tag_id,t.name
                FROM skill_tags st
                JOIN tags t ON t.tag_id=st.tag_id
                WHERE st.skill_id IN ({placeholders})
                ORDER BY t.name,t.tag_id
                """,
                skill_ids,
            ):
                result[str(row["skill_id"])]["tags"].append(
                    {"tag_id": row["tag_id"], "name": row["name"]}
                )
        return result

    def skills_page(
        self,
        *,
        query: str = "",
        source_class: str | None = None,
        authority_tier: int | None = None,
        category_id: str | None = None,
        tag_id: str | None = None,
        sort: str = "name",
        cursor: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        terms = [part.casefold() for part in query.split() if part.strip()]
        category_skills: set[str] | None = None
        tag_skills: set[str] | None = None
        with self._db() as db:
            if category_id:
                category_skills = {
                    str(row["skill_id"])
                    for row in db.connection.execute(
                        "SELECT skill_id FROM skill_categories WHERE category_id=?",
                        (category_id,),
                    )
                }
            if tag_id:
                tag_skills = {
                    str(row["skill_id"])
                    for row in db.connection.execute(
                        "SELECT skill_id FROM skill_tags WHERE tag_id=?",
                        (tag_id,),
                    )
                }
        rows: list[dict[str, Any]] = []
        for row in self.registry.records():
            if source_class and str(row.get("source_class")) != source_class:
                continue
            if authority_tier is not None and int(row.get("authority_tier", 0)) != authority_tier:
                continue
            skill_id = str(row["skill_id"])
            if category_skills is not None and skill_id not in category_skills:
                continue
            if tag_skills is not None and skill_id not in tag_skills:
                continue
            haystack = " ".join(
                [
                    str(row.get("name", "")),
                    str(row.get("description", "")),
                    str(row.get("path", "")),
                    str(row.get("source_class", "")),
                ]
            ).casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            item = dict(row)
            variants = self.registry.variants_for(skill_id)
            item["variant_count"] = len(variants)
            item["nonselectable_variant_count"] = sum(
                1 for variant in variants if not bool(variant.get("selectable"))
            )
            rows.append(item)
        if sort == "authority":
            rows.sort(
                key=lambda row: (-int(row.get("authority_tier", 0)), str(row["name"]).casefold())
            )
        elif sort == "source":
            rows.sort(
                key=lambda row: (str(row.get("source_class", "")), str(row["name"]).casefold())
            )
        else:
            rows.sort(key=lambda row: str(row["name"]).casefold())
        page = self._page(rows, cursor, limit)
        organizations = self._organization_map([str(item["skill_id"]) for item in page["items"]])
        for item in page["items"]:
            item["organization"] = organizations[str(item["skill_id"])]
        page["facets"] = {
            **self.skill_facets(),
            "categories": self.categories_list(),
            "tags": self.tags_list(),
        }
        return page

    def discovery_issues_page(self, *, cursor: int = 0, limit: int = 50) -> dict[str, Any]:
        return self._page(
            [dict(row) for row in self.registry.payload().get("invalid", [])], cursor, limit
        )

    def skill_metadata(self, skill_id: str) -> dict[str, Any]:
        row = self.registry.find(skill_id)
        if row is None:
            raise ValidationError(f"unknown-skill-id:{skill_id}")
        return {**row, "variants": self.registry.variants_for(skill_id)}

    def skill_body(self, skill_id: str) -> dict[str, Any]:
        return self.registry.get(skill_id)

    def skill_resources(self, skill_id: str) -> dict[str, Any]:
        """Read the selected Skill's internal text capability bundle on demand.

        This intentionally stays inside the selected canonical Skill directory and
        excludes dependency/build trees. It is not a generic filesystem endpoint.
        """
        metadata = self.skill_metadata(skill_id)
        skill_file = Path(str(metadata["path"])).expanduser().resolve()
        root = skill_file.parent.resolve()
        if not skill_file.is_file():
            raise ValidationError(f"skill-file-missing:{skill_id}")

        candidates: list[Path] = []
        skipped: list[dict[str, Any]] = []
        for path in root.rglob("*"):
            if not path.is_file() or path == skill_file:
                continue
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            try:
                resolved = path.resolve()
            except OSError:
                skipped.append({"path": relative.as_posix(), "reason": "resolve-failed"})
                continue
            if not _path_within_root(resolved, root):
                skipped.append({"path": relative.as_posix(), "reason": "outside-skill-root"})
                continue
            if any(
                part.casefold() in _SKILL_RESOURCE_EXCLUDED_DIRS for part in relative.parts[:-1]
            ):
                continue
            if path.suffix.casefold() not in _SKILL_RESOURCE_SUFFIXES:
                continue
            candidates.append(path)

        def priority(path: Path) -> tuple[int, int, str]:
            relative = path.relative_to(root)
            folded = [part.casefold() for part in relative.parts]
            route_like = (
                relative.name.casefold() in {"routes.md", "route.md"}
                or "routes" in folded
                or "references" in folded
            )
            return (0 if route_like else 1, len(relative.parts), str(relative).casefold())

        resources: list[dict[str, Any]] = []
        total_bytes = 0
        truncated = False
        for path in sorted(candidates, key=priority):
            relative = path.relative_to(root)
            try:
                size = path.stat().st_size
            except OSError:
                skipped.append({"path": relative.as_posix(), "reason": "stat-failed"})
                continue
            if size > _SKILL_RESOURCE_MAX_FILE_BYTES:
                skipped.append(
                    {"path": relative.as_posix(), "reason": "file-too-large", "bytes": size}
                )
                truncated = True
                continue
            if (
                len(resources) >= _SKILL_RESOURCE_MAX_FILES
                or total_bytes + size > _SKILL_RESOURCE_MAX_TOTAL_BYTES
            ):
                truncated = True
                break
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skipped.append({"path": relative.as_posix(), "reason": "not-utf8-text"})
                continue
            resources.append(
                {
                    "path": relative.as_posix(),
                    "type": _skill_resource_type(path),
                    "content": content,
                    "bytes": size,
                    "truncated": False,
                }
            )
            total_bytes += size

        return {
            "skill_id": str(metadata["skill_id"]),
            "root": str(root),
            "resources": resources,
            "resource_count": len(resources),
            "total_bytes": total_bytes,
            "truncated": truncated,
            "skipped": skipped,
        }

    def _followed_skill_resources(
        self,
        skill: dict[str, Any],
        content: str,
        resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_path = {
            _normalize_resource_path(str(resource.get("path", ""))).casefold(): resource
            for resource in resources
            if resource.get("path")
        }
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        queue = _referenced_resource_paths(content)
        while queue and len(selected) < _SKILL_RESOURCE_MAX_FILES:
            requested = _normalize_resource_path(str(queue.pop(0))).casefold()
            resource = by_path.get(requested)
            if resource is None or requested in seen:
                continue
            seen.add(requested)
            selected.append(resource)
            for nested in _referenced_resource_paths(str(resource.get("content", ""))):
                nested_key = _normalize_resource_path(nested).casefold()
                if nested_key not in seen:
                    queue.append(nested)

        if selected or _capability_kind(skill, content) != "router":
            return selected
        return [
            resource
            for resource in resources
            if _route_like_resource(str(resource.get("path", "")))
        ][:_SKILL_RESOURCE_MAX_FILES]

    def _explicit_child_skills(
        self,
        skill_id: str,
        text: str,
        *,
        route_text: str = "",
        task: str = "",
    ) -> list[dict[str, Any]]:
        discovered: list[str] = []
        seen: set[str] = {skill_id.casefold()}
        known_ids = {
            str(row.get("skill_id", "")).casefold()
            for row in self.registry.records()
            if row.get("skill_id")
        }

        def add(value: str) -> None:
            candidate = value.strip().casefold()
            if not candidate or candidate in seen:
                return
            if candidate not in known_ids:
                return
            seen.add(candidate)
            discovered.append(candidate)

        for pattern in _CHILD_SKILL_PATTERNS:
            for match in pattern.finditer(text):
                add(str(match.group(1) or ""))

        # Route documents often list canonical Skill ids without surrounding prose.
        # Only route text gets this permissive token pass; ordinary references do not.
        for match in _SKILL_TOKEN_RE.finditer(route_text):
            add(str(match.group(1) or ""))

        ranks: dict[str, int] = {}
        scores: dict[str, int] = {}
        if task.strip():
            task_terms = _task_relevance_terms(task)
            route_lines = route_text.splitlines()
            for child_id in discovered:
                row = self.registry.find(child_id) or {}
                route_context = "\n".join(
                    line for line in route_lines if child_id in line.casefold()
                )
                haystack = "\n".join(
                    str(value)
                    for value in (
                        row.get("name"),
                        row.get("description"),
                        route_context,
                    )
                    if value
                ).casefold()
                score = 0
                for term in task_terms:
                    if term in haystack:
                        score += max(1, len(term) - 1)
                scores[child_id] = score
            ranked = sorted(
                (child_id for child_id in discovered if scores.get(child_id, 0) > 0),
                key=lambda child_id: (
                    -scores[child_id],
                    discovered.index(child_id),
                ),
            )
            ranks = {child_id: index + 1 for index, child_id in enumerate(ranked)}
            discovery_order = {value: index for index, value in enumerate(discovered)}
            discovered.sort(key=lambda value: (ranks.get(value, 10_000), discovery_order[value]))

        return [
            {
                "skill_id": child_id,
                "task_rank": ranks.get(child_id),
                "task_matched": child_id in ranks if task.strip() else None,
                "task_score": scores.get(child_id) if task.strip() else None,
            }
            for child_id in discovered
        ]

    def skill_resolve(
        self,
        skill_id: str,
        *,
        task: str = "",
        max_depth: int = _SKILL_RESOLVE_DEFAULT_DEPTH,
        max_skills: int = _SKILL_RESOLVE_DEFAULT_SKILLS,
        max_total_bytes: int = _SKILL_RESOLVE_DEFAULT_BYTES,
    ) -> dict[str, Any]:
        """Resolve one Skill into a bounded recursive executable capability tree."""
        depth_limit = max(0, min(int(max_depth), _SKILL_RESOLVE_MAX_DEPTH))
        skill_limit = max(1, min(int(max_skills), _SKILL_RESOLVE_MAX_SKILLS))
        byte_limit = max(
            64 * 1024,
            min(int(max_total_bytes), _SKILL_RESOLVE_MAX_BYTES),
        )
        visited: set[str] = set()
        unresolved: list[str] = []
        state = {
            "skills": 0,
            "bytes": 0,
            "truncated": False,
        }

        def compact_skill(body: dict[str, Any]) -> dict[str, Any]:
            return {
                key: body.get(key)
                for key in (
                    "skill_id",
                    "variant_id",
                    "name",
                    "description",
                    "path",
                    "root",
                    "sha256",
                    "source_class",
                    "authority_tier",
                    "selectable",
                    "priority",
                    "category_router",
                )
            } | {"content": body.get("content", "")}

        def resolve_node(current_id: str, depth: int) -> dict[str, Any]:
            normalized = current_id.casefold()
            if normalized in visited:
                return {"skill_id": normalized, "cycle": True, "children": []}
            if state["skills"] >= skill_limit:
                state["truncated"] = True
                return {"skill_id": normalized, "truncated": "skill-limit", "children": []}

            body = self.skill_body(normalized)
            metadata = self.skill_metadata(normalized)
            visited.add(normalized)
            state["skills"] += 1
            root_content = str(body.get("content", ""))
            root_bytes = len(root_content.encode("utf-8"))
            state["bytes"] += root_bytes
            if state["bytes"] > byte_limit:
                state["truncated"] = True

            bundle = self.skill_resources(normalized)
            resources = list(bundle.get("resources", []))
            followed = self._followed_skill_resources(metadata, root_content, resources)
            remaining = max(0, byte_limit - int(state["bytes"]))
            included_resources: list[dict[str, Any]] = []
            for resource in followed:
                content = str(resource.get("content", ""))
                size = len(content.encode("utf-8"))
                if size > remaining:
                    state["truncated"] = True
                    break
                included_resources.append(resource)
                state["bytes"] += size
                remaining -= size

            execution_text = root_content + "".join(
                f"\n\n# Followed capability resource: {resource.get('path', '')}\n"
                + str(resource.get("content", ""))
                for resource in included_resources
            )
            kind = _capability_kind(metadata, execution_text)
            route_text = root_content if kind == "router" else ""
            route_text += "".join(
                "\n" + str(resource.get("content", ""))
                for resource in included_resources
                if _route_like_resource(str(resource.get("path", "")))
            )
            child_refs = self._explicit_child_skills(
                normalized,
                execution_text,
                route_text=route_text,
                task=task,
            )
            selected_child_refs = child_refs
            if kind == "router" and task.strip():
                matched = [row for row in child_refs if row.get("task_rank") is not None]
                if matched:
                    selected_child_refs = matched[:1]
                else:
                    selected_child_refs = []
                selected_ids = {str(row["skill_id"]) for row in selected_child_refs}
                for row in child_refs:
                    row["selected"] = str(row["skill_id"]) in selected_ids
            children: list[dict[str, Any]] = []
            if depth < depth_limit and state["bytes"] < byte_limit:
                for child in selected_child_refs:
                    child_id = str(child["skill_id"])
                    try:
                        node = resolve_node(child_id, depth + 1)
                    except (KeyError, OSError, UnicodeError, ValueError):
                        unresolved.append(child_id)
                        node = {"skill_id": child_id, "unresolved": True, "children": []}
                    node["task_rank"] = child.get("task_rank")
                    node["task_matched"] = child.get("task_matched")
                    children.append(node)
                    if state["skills"] >= skill_limit or state["bytes"] >= byte_limit:
                        state["truncated"] = True
                        break

            return {
                "skill": compact_skill(body),
                "analysis": {
                    "kind": kind,
                    "recursive": bool(kind != "single" or child_refs or included_resources),
                    "candidate_children": child_refs,
                    "resource_count": int(bundle.get("resource_count", len(resources))),
                    "resource_paths": [str(resource.get("path", "")) for resource in resources],
                    "followed_resource_paths": [
                        str(resource.get("path", "")) for resource in included_resources
                    ],
                    "resource_bundle_truncated": bool(bundle.get("truncated")),
                },
                "resources": included_resources,
                "children": children,
            }

        root = resolve_node(skill_id, 0)
        return {
            "skill_id": skill_id.casefold(),
            "task": task or None,
            "resolution": root,
            "summary": {
                "loaded_skill_count": int(state["skills"]),
                "loaded_bytes": int(state["bytes"]),
                "max_depth": depth_limit,
                "max_skills": skill_limit,
                "max_total_bytes": byte_limit,
                "truncated": bool(state["truncated"]),
                "unresolved_child_skills": sorted(set(unresolved)),
            },
            "contract": {
                "entry_point": "Complete canonical SKILL.md is always loaded first.",
                "resources": (
                    "Only explicitly referenced internal text resources are followed; "
                    "Router Skills fall back to route files when no explicit file path is present."
                ),
                "children": (
                    "Only canonical child Skills explicitly named by the loaded capability text "
                    "are recursively loaded."
                ),
                "no_flatten": True,
            },
        }

    def skill_validate(self, skill_id: str, variant_id: str | None = None) -> dict[str, Any]:
        metadata = self.skill_metadata(skill_id)
        path = str(metadata["path"])
        if variant_id:
            variant = next(
                (row for row in metadata["variants"] if str(row.get("variant_id")) == variant_id),
                None,
            )
            if variant is None:
                raise ValidationError(f"unknown-variant-id:{variant_id}")
            path = str(variant["path"])
        return validate_skill_file(Path(path))

    def skill_evaluate(self, skill_id: str, query: str) -> dict[str, Any]:
        if not query.strip():
            raise ValidationError("evaluation-query-required")
        return self.registry.evaluate(skill_id, query)

    def sources_list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return ManagementService(db).list_sources()

    def sources_page(self, *, cursor: int = 0, limit: int = 100) -> dict[str, Any]:
        return self._page(self.sources_list(), cursor, limit)

    def categories_list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.connection.execute("""
                SELECT c.category_id,c.name,c.description,COUNT(sc.skill_id) AS skill_count
                FROM categories c LEFT JOIN skill_categories sc ON sc.category_id=c.category_id
                GROUP BY c.category_id,c.name,c.description
                ORDER BY c.name COLLATE NOCASE,c.category_id
            """)
            return [
                {
                    "category_id": row["category_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "skill_count": int(row["skill_count"]),
                }
                for row in rows
            ]

    def category_upsert(
        self, name: str, description: str = "", *, dry_run: bool = False
    ) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).upsert_category(name, description, dry_run=dry_run)

    def category_delete(self, category_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).delete_category(category_id, dry_run=dry_run)

    def tags_list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.connection.execute("""
                SELECT t.tag_id,t.name,COUNT(st.skill_id) AS skill_count
                FROM tags t LEFT JOIN skill_tags st ON st.tag_id=t.tag_id
                GROUP BY t.tag_id,t.name ORDER BY t.name COLLATE NOCASE,t.tag_id
            """)
            return [
                {
                    "tag_id": row["tag_id"],
                    "name": row["name"],
                    "skill_count": int(row["skill_count"]),
                }
                for row in rows
            ]

    def tag_upsert(self, name: str, *, dry_run: bool = False) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).upsert_tag(name, dry_run=dry_run)

    def tag_delete(self, tag_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).delete_tag(tag_id, dry_run=dry_run)

    def skill_organization_get(self, skill_id: str) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).get_skill_organization(skill_id)

    def skill_category_bind(
        self, skill_id: str, category_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).bind_category(skill_id, category_id, dry_run=dry_run)

    def skill_tag_bind(
        self, skill_id: str, tag_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).bind_tag(skill_id, tag_id, dry_run=dry_run)

    def skill_category_unbind(
        self, skill_id: str, category_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).unbind_category(skill_id, category_id, dry_run=dry_run)

    def skill_tag_unbind(
        self, skill_id: str, tag_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        with self._db() as db:
            return ManagementService(db).unbind_tag(skill_id, tag_id, dry_run=dry_run)

    def workspaces_list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return ManagementService(db).list_workspaces()

    def agents_list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return ManagementService(db).list_agents()

    def workflow_list(
        self, *, name: str | None = None, cursor: int = 0, limit: int = 50,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        with self._db() as db:
            page = WorkflowService(db).list_workflows(
                cursor=0, limit=200, include_archived=include_archived
            )
        items = page["items"]
        if name:
            items = [row for row in items if name.casefold() in str(row.get("name", "")).casefold()]
        return self._page(items, cursor, limit)

    def workflow_search(self, query: str, *, cursor: int = 0, limit: int = 50) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).search_workflows(
                query,
                cursor=cursor,
                limit=limit,
            )

    def workflow_get(self, workflow_id: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).get_workflow(workflow_id)

    def workflow_usage(self, workflow_id: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).workflow_usage(workflow_id)

    def workflow_archive(self, workflow_id: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).archive_workflow(workflow_id)

    def workflow_restore(self, workflow_id: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).restore_workflow(workflow_id)

    def workflow_family_archive(self, name: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).archive_workflow_family(name)

    def workflow_delete(self, workflow_id: str) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).delete_workflow_permanently(workflow_id)

    def workflow_create(self, spec: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).create_workflow(spec, dry_run=dry_run)

    def workflow_plan(
        self, workflow_id: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).plan(workflow_id, context)

    def workflow_prompt(
        self, workflow_id: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._db() as db:
            return WorkflowService(db).prompt(workflow_id, context)

    def run_list(
        self,
        *,
        status: str | None = None,
        workflow_id: str | None = None,
        skill_id: str | None = None,
        cursor: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._db() as db:
            rows = db.connection.execute(
                "SELECT r.run_id,r.workflow_id,r.status,r.current_stage_id,r.context_json,"
                "r.created_at,r.updated_at,w.name AS workflow_name,w.version AS workflow_version,"
                "s.stage_key AS current_stage_key "
                "FROM workflow_runs r JOIN workflows w ON w.workflow_id=r.workflow_id "
                "LEFT JOIN workflow_stages s ON s.stage_id=r.current_stage_id "
                "ORDER BY r.updated_at DESC,r.run_id"
            ).fetchall()
            resolved_by_run: dict[str, set[str]] = {}
            for stage in db.connection.execute(
                "SELECT run_id,resolved_bindings_json FROM workflow_run_stages"
            ):
                bucket = resolved_by_run.setdefault(str(stage["run_id"]), set())
                for binding in json_value(stage["resolved_bindings_json"], []):
                    if binding.get("skill_id"):
                        bucket.add(str(binding["skill_id"]))
            items: list[dict[str, Any]] = []
            for row in rows:
                if status and row["status"] != status:
                    continue
                if workflow_id and row["workflow_id"] != workflow_id:
                    continue
                resolved_skill_ids = sorted(resolved_by_run.get(str(row["run_id"]), set()))
                if skill_id and skill_id.casefold() not in {
                    item.casefold() for item in resolved_skill_ids
                }:
                    continue
                context = json_value(row["context_json"], {})
                item = dict(row)
                item.pop("context_json", None)
                item["context"] = context
                item["task"] = context.get("task") if isinstance(context, dict) else None
                item["resolved_skill_ids"] = resolved_skill_ids
                items.append(item)
        return self._page(items, cursor, limit)

    def run_get(self, run_id: str) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).snapshot(run_id)

    def run_create(
        self,
        workflow_id: str,
        context: dict[str, Any] | None = None,
        run_key: str | None = None,
    ) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).create_run(workflow_id, context, run_key=run_key)

    def run_start(self, run_id: str) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).start(run_id)

    def run_block(self, run_id: str, reason: str) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).block(run_id, reason)

    def run_evidence_add(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        evidence_key: str | None = None,
    ) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).add_evidence(run_id, kind, payload, evidence_key=evidence_key)

    def run_resume(self, run_id: str) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).resume(run_id)

    def run_succeed(self, run_id: str, gate_result: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._db() as db:
            return RunService(db).succeed_current(run_id, gate_result)

    def deployment_plan(
        self,
        skill_id: str,
        operation: str,
        source_path: str | None = None,
        target_path: str | None = None,
    ) -> dict[str, Any]:
        with self._db() as db:
            service = DeploymentService(
                db,
                protected_roots=DEFAULT_PROTECTED_ROOTS,
                managed_roots=(DEFAULT_MANAGED_ROOT,),
            )
            return service.plan(
                skill_id,
                operation,
                source_path=source_path,
                target_path=target_path,
            )

    def deployment_transactions_list(
        self,
        *,
        state: str | None = None,
        skill_id: str | None = None,
        cursor: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._db() as db:
            rows = db.connection.execute(
                "SELECT transaction_id,plan_id,skill_id,operation,state,source_path,"
                "target_path,ownership_class,source_digest,target_digest,"
                "rollback_state,created_at,updated_at FROM deployment_transactions "
                "ORDER BY updated_at DESC,transaction_id"
            )
            items = [
                dict(row)
                for row in rows
                if (not state or row["state"] == state)
                and (not skill_id or row["skill_id"] == skill_id)
            ]
        return self._page(items, cursor, limit)

    def managed_locations_list(
        self, *, skill_id: str | None = None, cursor: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        with self._db() as db:
            rows = db.connection.execute(
                "SELECT path,skill_id,ownership_class,content_digest,origin_transaction_id,"
                "created_at,updated_at FROM managed_paths WHERE active=1 "
                "ORDER BY updated_at DESC,path"
            )
            items = [dict(row) for row in rows if not skill_id or row["skill_id"] == skill_id]
        return self._page(items, cursor, limit)

    def audit_list(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        cursor: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._db() as db:
            rows = db.connection.execute(
                "SELECT audit_id,action,entity_type,entity_id,payload_json,created_at "
                "FROM audit_log ORDER BY audit_id DESC"
            )
            items = []
            for row in rows:
                if entity_type and row["entity_type"] != entity_type:
                    continue
                if entity_id and row["entity_id"] != entity_id:
                    continue
                if action and row["action"] != action:
                    continue
                items.append(
                    {
                        "audit_id": int(row["audit_id"]),
                        "action": row["action"],
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                        "payload": json_value(row["payload_json"], {}),
                        "created_at": row["created_at"],
                    }
                )
        return self._page(items, cursor, limit)

    def runtime_health(self) -> dict[str, Any]:
        snapshot = self.registry.payload()
        with self._db() as db:
            parity = RegistryStore(db).parity(snapshot)
            integrity = db.integrity()
            active = int(
                db.connection.execute(
                    "SELECT COUNT(*) FROM deployment_transactions WHERE state IN "
                    "('planned','validated','applying','verifying','recovery_required','rolling_back')"
                ).fetchone()[0]
            )
        listeners = {str(port): self._port_open(port) for port in (9330, 8941, 8942, 8943)}
        trustworthy = (
            bool(parity.get("ok"))
            and integrity.get("integrity_check") == ["ok"]
            and not integrity.get("foreign_key_violations")
        )
        return {
            "ok": trustworthy and listeners["8943"],
            "mutations_allowed": trustworthy,
            "registry": self.registry.status(),
            "parity": parity,
            "integrity": integrity,
            "active_deployment_transactions": active,
            "runtime": {
                "gateway": {"port": 9330, "listening": listeners["9330"]},
                "legacy": {"port": 8941, "listening": listeners["8941"]},
                "rollback": {"port": 8942, "listening": listeners["8942"]},
                "current": {"port": 8943, "listening": listeners["8943"]},
            },
        }

    @staticmethod
    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                return True
        except OSError:
            return False

    def skill_open_folder(self, skill_id: str, variant_id: str | None = None) -> dict[str, Any]:
        if self.explorer_opener is None:
            raise ManagerError("explorer-opener-unavailable")
        metadata = self.skill_metadata(skill_id)
        path = Path(str(metadata["path"])).expanduser().absolute()
        if variant_id:
            variant = next(
                (row for row in metadata["variants"] if str(row.get("variant_id")) == variant_id),
                None,
            )
            if variant is None:
                raise ValidationError(f"unknown-variant-id:{variant_id}")
            path = Path(str(variant["path"])).expanduser().absolute()
        if path.name.casefold() != "skill.md" or not path.is_file():
            raise ManagerError("skill-path-not-found")
        folder = path.parent
        self.explorer_opener(folder)
        return {
            "opened": True,
            "path": str(folder),
            "skill_id": skill_id,
            "variant_id": variant_id,
        }
