from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .search_terms import normalized_search_terms

_NAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$")
_MAX_SKILL_BYTES = 512_000
_ARCHIVE_PARTS = {
    ".trash",
    "archive",
    "archives",
    "backup",
    "backups",
    "retired",
    "venv",
}
_ARCHIVE_SUBSTRINGS = (
    "final-acceptance",
    "backup-pre-",
    "pre-unify",
)


@dataclass(frozen=True)
class SourceRoot:
    source_class: str
    path: Path
    authority_tier: int
    selectable: bool = True


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    variant_id: str
    name: str
    description: str
    path: str
    root: str
    sha256: str
    size: int
    source_class: str
    authority_tier: int
    selectable: bool
    priority: int
    category_router: bool


def _absolute(path: Path) -> Path:
    return path.expanduser().absolute()


def _path_key(path: Path | str) -> str:
    return os.path.normcase(str(_absolute(Path(path))))


def _is_under(path: Path, root: Path) -> bool:
    path_key = _path_key(path)
    root_key = _path_key(root).rstrip("\\/")
    return path_key == root_key or path_key.startswith(root_key + os.sep)


def _archive_like(path: Path) -> bool:
    lowered_parts = {part.casefold() for part in path.parts}
    if lowered_parts & _ARCHIVE_PARTS:
        return True
    text = str(path).casefold()
    return any(marker in text for marker in _ARCHIVE_SUBSTRINGS)


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    normalized = text.replace("\r\n", "\n")
    match = _FRONTMATTER_RE.match(normalized)
    if not match:
        return {}, normalized
    fields: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        field = _FIELD_RE.match(raw)
        if not field:
            continue
        value = field.group(2).strip().strip('"').strip("'")
        fields[field.group(1).lower()] = value
    return fields, normalized[match.end() :]


def validate_skill_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "ok": False,
            "errors": [f"read-failed:{type(exc).__name__}"],
            "path": str(path),
        }
    if len(raw) > _MAX_SKILL_BYTES:
        return {"ok": False, "errors": ["skill-too-large"], "path": str(path)}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "errors": ["not-utf8"], "path": str(path)}
    fields, _body = _frontmatter(text)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    errors: list[str] = []
    if not name:
        errors.append("missing-name")
    elif not _NAME_RE.fullmatch(name):
        errors.append("invalid-name")
    if not description:
        errors.append("missing-description")
    return {
        "ok": not errors,
        "errors": errors,
        "name": name,
        "description": description,
        "path": str(path),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _iter_skill_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    try:
        for path in root.rglob("SKILL.md"):
            lowered = {part.casefold() for part in path.parts}
            if ".git" in lowered or "node_modules" in lowered or "__pycache__" in lowered:
                continue
            found.append(path)
    except OSError:
        pass
    return sorted(found, key=lambda item: _path_key(item))


def _category_router(path: Path, name: str) -> bool:
    routes = path.parent / "references" / "routes.md"
    return name.casefold().startswith("category-") or routes.is_file()


def _dedupe_roots(roots: list[SourceRoot]) -> list[SourceRoot]:
    chosen: dict[str, SourceRoot] = {}
    for root in roots:
        key = _path_key(root.path)
        previous = chosen.get(key)
        if previous is None or root.authority_tier > previous.authority_tier:
            chosen[key] = SourceRoot(
                root.source_class,
                _absolute(root.path),
                root.authority_tier,
                root.selectable,
            )
    return sorted(
        chosen.values(),
        key=lambda row: (-row.authority_tier, _path_key(row.path), row.source_class),
    )


def _source_for_path(path: Path, roots: list[SourceRoot], *, explicit: bool) -> SourceRoot:
    if _archive_like(path):
        return SourceRoot("historical_archive", path.parent, 0, False)
    matches = [root for root in roots if _is_under(path, root.path)]
    if matches:
        matches.sort(key=lambda row: (-row.authority_tier, -len(_path_key(row.path))))
        return matches[0]
    if explicit:
        return SourceRoot("historical_explicit", path.parent, 100, True)
    return SourceRoot("configured_active", path.parent, 600, True)


def _record(path: Path, source: SourceRoot, checked: dict[str, Any]) -> SkillRecord:
    absolute = _absolute(path)
    name = str(checked["name"])
    variant_material = f"{_path_key(absolute)}\0{checked['sha256']}".encode()
    return SkillRecord(
        skill_id=name.casefold(),
        variant_id=hashlib.sha256(variant_material).hexdigest()[:24],
        name=name,
        description=str(checked["description"]),
        path=str(absolute),
        root=str(_absolute(source.path)),
        sha256=str(checked["sha256"]),
        size=int(checked["size"]),
        source_class=source.source_class,
        authority_tier=source.authority_tier,
        selectable=source.selectable,
        priority=source.authority_tier,
        category_router=_category_router(absolute, name),
    )


class Registry:
    def __init__(
        self,
        roots: list[SourceRoot],
        explicit_files: list[Path] | None = None,
        *,
        index_path: Path | None = None,
        legacy_config_path: Path | None = None,
    ) -> None:
        self.roots = _dedupe_roots(roots)
        self.explicit_files = [_absolute(path) for path in (explicit_files or [])]
        self.index_path = _absolute(index_path) if index_path else None
        self.legacy_config_path = _absolute(legacy_config_path) if legacy_config_path else None
        self._payload: dict[str, Any] | None = None

    def load_existing_index(self) -> dict[str, Any]:
        """Load the existing M01 snapshot without scanning Skill roots."""
        if self.index_path is None:
            raise RuntimeError("registry-index-path-unavailable")
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("registry-index-unreadable") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("registry-index-invalid")
        if not isinstance(payload.get("skills"), list):
            raise RuntimeError("registry-index-invalid")
        if not isinstance(payload.get("variants"), dict):
            raise RuntimeError("registry-index-invalid")
        if not isinstance(payload.get("invalid"), list):
            raise RuntimeError("registry-index-invalid")
        self._payload = payload
        return payload

    def build_index(self) -> dict[str, Any]:
        invalid: list[dict[str, Any]] = []
        by_path: dict[str, SkillRecord] = {}

        def add(path: Path, source: SourceRoot, *, explicit: bool) -> None:
            checked = validate_skill_file(path)
            if not checked["ok"]:
                invalid.append({"path": str(path), "errors": checked["errors"]})
                return
            resolved_source = _source_for_path(path, self.roots, explicit=explicit)
            if source.authority_tier > resolved_source.authority_tier and not _archive_like(path):
                resolved_source = source
            record = _record(path, resolved_source, checked)
            key = _path_key(path)
            previous = by_path.get(key)
            if previous is None or (
                record.authority_tier,
                record.selectable,
                record.source_class,
            ) > (
                previous.authority_tier,
                previous.selectable,
                previous.source_class,
            ):
                by_path[key] = record

        for root in self.roots:
            for path in _iter_skill_files(root.path):
                add(path, root, explicit=False)

        for path in sorted(self.explicit_files, key=_path_key):
            source = _source_for_path(path, self.roots, explicit=True)
            add(path, source, explicit=True)

        variants: dict[str, list[SkillRecord]] = {}
        for record in by_path.values():
            variants.setdefault(record.skill_id, []).append(record)

        selected: list[SkillRecord] = []
        serialized_variants: dict[str, list[dict[str, Any]]] = {}
        for skill_id, rows in variants.items():
            rows.sort(
                key=lambda row: (
                    -int(row.selectable),
                    -row.authority_tier,
                    _path_key(row.path),
                    row.sha256,
                )
            )
            eligible = [row for row in rows if row.selectable]
            if eligible:
                selected.append(eligible[0])
            serialized_variants[skill_id] = [asdict(row) for row in rows]

        selected.sort(key=lambda row: (row.name.casefold(), _path_key(row.path)))
        nonselectable = sum(1 for rows in variants.values() for row in rows if not row.selectable)
        payload: dict[str, Any] = {
            "schema_version": 2,
            "source_policy": "explicit-authority-v1",
            "generated_at": time.time(),
            "skill_count": len(selected),
            "variant_count": len(by_path),
            "nonselectable_variant_count": nonselectable,
            "invalid_count": len(invalid),
            "explicit_file_count": len(self.explicit_files),
            "roots": [
                {
                    "source_class": root.source_class,
                    "path": str(root.path),
                    "authority_tier": root.authority_tier,
                    "selectable": root.selectable,
                }
                for root in self.roots
            ],
            "skills": [asdict(row) for row in selected],
            "variants": serialized_variants,
            "invalid": invalid[:1000],
        }
        self._payload = payload
        if self.index_path:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temp.replace(self.index_path)
        return payload

    def payload(self, *, force: bool = False) -> dict[str, Any]:
        if force or self._payload is None:
            return self.build_index()
        return self._payload

    def records(self) -> list[dict[str, Any]]:
        return list(self.payload().get("skills", []))

    def find(self, name: str) -> dict[str, Any] | None:
        key = name.casefold()
        return next(
            (row for row in self.records() if str(row.get("skill_id", "")).casefold() == key),
            None,
        )

    def variants_for(self, name: str) -> list[dict[str, Any]]:
        return list(self.payload().get("variants", {}).get(name.casefold(), []))

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        terms = normalized_search_terms(query)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for row in self.records():
            name = str(row.get("name", ""))
            description = str(row.get("description", ""))
            haystack = f"{name} {description} {row.get('path', '')}".casefold()
            score = 0
            for term in terms:
                if term in name.casefold():
                    score += 8
                if term in description.casefold():
                    score += 4
                if term in haystack:
                    score += 1
            if not terms or score:
                scored.append((score, name.casefold(), row))
        scored.sort(key=lambda item: (-item[0], item[1], _path_key(item[2]["path"])))
        return [row for _score, _name, row in scored[: max(1, min(limit, 100))]]

    def get(self, name: str) -> dict[str, Any]:
        row = self.find(name)
        if row is None:
            raise KeyError(name)
        raw = Path(str(row["path"])).read_bytes()
        if len(raw) > _MAX_SKILL_BYTES:
            raise ValueError("skill-too-large")
        return {
            **row,
            "content": raw.decode("utf-8"),
            "variants": self.variants_for(name),
        }

    def evaluate(self, name: str, query: str) -> dict[str, Any]:
        row = self.find(name)
        if row is None:
            raise KeyError(name)
        ranked = self.search(query, limit=100)
        rank = next(
            (
                index + 1
                for index, item in enumerate(ranked)
                if str(item["skill_id"]).casefold() == name.casefold()
            ),
            None,
        )
        return {"name": row["name"], "query": query, "rank": rank, "matched": rank is not None}

    def status(self) -> dict[str, Any]:
        payload = self.payload()
        return {
            "ok": True,
            "source_policy": payload["source_policy"],
            "skill_count": payload["skill_count"],
            "variant_count": payload["variant_count"],
            "nonselectable_variant_count": payload["nonselectable_variant_count"],
            "invalid_count": payload["invalid_count"],
            "explicit_file_count": payload["explicit_file_count"],
            "roots": payload["roots"],
            "legacy_config_path": str(self.legacy_config_path) if self.legacy_config_path else None,
            "index_path": str(self.index_path) if self.index_path else None,
        }


def _machine_config_for_home(home: Path) -> Path:
    return home / "AppData" / "Local" / "WebGPT-as-Codex" / "skills" / "config.json"


def _user_home() -> Path:
    override = os.getenv("SKILLS_MANAGER_USER_HOME") or os.getenv(
        "SKILL_CONTROL_PLANE_USER_HOME"
    )
    if override:
        return _absolute(Path(override))
    for key in ("USERPROFILE", "HOME"):
        value = os.getenv(key)
        if value:
            return _absolute(Path(value))
    try:
        return _absolute(Path.home())
    except RuntimeError as exc:
        raise RuntimeError("Could not determine Skills Manager user home.") from exc

def _legacy_config_path() -> Path:
    override = os.getenv("SKILLS_MANAGER_LEGACY_CONFIG") or os.getenv(
        "SKILL_CONTROL_PLANE_LEGACY_CONFIG"
    )
    if override:
        return _absolute(Path(override))
    user_home_override = os.getenv("SKILLS_MANAGER_USER_HOME") or os.getenv(
        "SKILL_CONTROL_PLANE_USER_HOME"
    )
    if user_home_override:
        return _machine_config_for_home(_absolute(Path(user_home_override)))
    local = os.getenv("LOCALAPPDATA")
    if local:
        return _absolute(Path(local) / "WebGPT-as-Codex" / "skills" / "config.json")
    return _machine_config_for_home(_user_home())

def _project_root() -> Path:
    override = os.getenv("SKILLS_MANAGER_PROJECT_ROOT") or os.getenv(
        "SKILL_CONTROL_PLANE_PROJECT_ROOT"
    )
    if override:
        return _absolute(Path(override))
    return _absolute(Path(__file__).resolve().parents[2])


def _workspace_root(project_root: Path) -> Path:
    override = os.getenv("SKILLS_MANAGER_WORKSPACE_ROOT") or os.getenv(
        "SKILL_CONTROL_PLANE_WORKSPACE_ROOT"
    )
    return _absolute(Path(override)) if override else project_root.parent


def _legacy_inputs(path: Path) -> tuple[list[Path], list[Path]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], []
    if not isinstance(payload, dict):
        return [], []
    roots = [Path(value) for value in payload.get("roots", []) if isinstance(value, str)]
    files = [Path(value) for value in payload.get("files", []) if isinstance(value, str)]
    return roots, files


def _classify_configured_root(path: Path) -> SourceRoot:
    text = _path_key(path).casefold()
    if "\\obsidian" in text:
        return SourceRoot("obsidian", path, 800)
    state_override = os.getenv("SKILLS_MANAGER_STATE_SKILLS_ROOT") or os.getenv(
        "SKILL_CONTROL_PLANE_STATE_SKILLS_ROOT"
    )
    if state_override:
        state_skills = _path_key(Path(state_override)).casefold()
        if text == state_skills or text.startswith(state_skills + os.sep):
            return SourceRoot("state_skills", path, 700)
    return SourceRoot("configured_active", path, 600)


def build_default_registry() -> Registry:
    project_root = _project_root()
    workspace_root = _workspace_root(project_root)
    legacy_config = _legacy_config_path()
    configured_roots, explicit_files = _legacy_inputs(legacy_config)

    roots = [
        SourceRoot("project_portable", workspace_root / ".skills", 1000),
        SourceRoot("shared_agents", _user_home() / ".agents" / "skills", 900),
        SourceRoot("codex_load", _user_home() / ".codex" / "skills", 850),
        SourceRoot("wac_active", workspace_root / "webgpt-as-codex" / "skills", 825),
        SourceRoot("claude_load", _user_home() / ".claude" / "skills", 650),
    ]
    roots.extend(_classify_configured_root(path) for path in configured_roots)

    extra = os.getenv("SKILLS_MANAGER_EXTRA_ROOTS") or os.getenv(
        "SKILL_CONTROL_PLANE_EXTRA_ROOTS", ""
    )
    if extra:
        roots.extend(
            SourceRoot("configured_active", Path(value), 600)
            for value in extra.split(os.pathsep)
            if value.strip()
        )

    state_override = os.getenv("SKILLS_MANAGER_STATE_DIR") or os.getenv(
        "SKILL_CONTROL_PLANE_STATE_DIR"
    )
    state_root = Path(state_override) if state_override else project_root / "runtime" / "state"
    return Registry(
        roots,
        explicit_files,
        index_path=state_root / "index.json",
        legacy_config_path=legacy_config,
    )
