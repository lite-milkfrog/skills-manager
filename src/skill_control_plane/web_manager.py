from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .core import build_default_registry
from .deployment import DeploymentPolicyError
from .explorer import ExplorerOpenError, open_explorer_folder
from .management import ValidationError
from .manager import PROJECT_ROOT, ManagerBackend, ManagerError
from .run_state import TransitionError
from .server import DEFAULT_DB

WEB_ROOT = PROJECT_ROOT / "web" / "manager"
MAX_JSON_BYTES = 1_048_576
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _one(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return values[0] if values else default


def _int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ManagerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        backend: ManagerBackend,
        web_root: Path = WEB_ROOT,
    ) -> None:
        super().__init__(address, ManagerHandler)
        self.backend = backend
        self.web_root = web_root


class ManagerHandler(BaseHTTPRequestHandler):
    server: ManagerHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, exc: Exception) -> None:
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        if isinstance(exc, KeyError):
            status = HTTPStatus.NOT_FOUND
        elif isinstance(exc, (TransitionError, DeploymentPolicyError)):
            status = HTTPStatus.CONFLICT
        elif isinstance(
            exc, (ValidationError, ManagerError, ExplorerOpenError, ValueError, TypeError)
        ):
            status = HTTPStatus.BAD_REQUEST
        self._json({"error": type(exc).__name__, "message": str(exc)}, int(status))

    def _body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        length = _int(raw_length, 0)
        if length < 0 or length > MAX_JSON_BYTES:
            raise ValueError("request-body-too-large")
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("json-object-required")
        return value

    def _mutation_guard(self) -> None:
        health = self.server.backend.runtime_health()
        if not health.get("mutations_allowed"):
            raise ManagerError("canonical-truth-degraded-mutations-disabled")

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [unquote(part) for part in path.split("/") if part]

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.removeprefix("/")
        candidate = (self.server.web_root / relative).resolve()
        root = self.server.web_root.resolve()
        if root not in candidate.parents and candidate != root:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = root / "index.html"
        raw = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._serve_static(parsed.path)
            return
        query = parse_qs(parsed.query)
        parts = self._parts(parsed.path)
        backend = self.server.backend
        try:
            if parts == ["api", "overview"]:
                payload = backend.overview()
            elif parts == ["api", "health"]:
                payload = backend.runtime_health()
            elif parts == ["api", "skills"]:
                tier_raw = _one(query, "authority_tier")
                payload = backend.skills_page(
                    query=_one(query, "query"),
                    source_class=_one(query, "source_class") or None,
                    authority_tier=_int(tier_raw, 0) if tier_raw else None,
                    category_id=_one(query, "category_id") or None,
                    tag_id=_one(query, "tag_id") or None,
                    sort=_one(query, "sort", "name"),
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif parts == ["api", "discovery-issues"]:
                payload = backend.discovery_issues_page(
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif parts == ["api", "sources"]:
                payload = backend.sources_list()
            elif parts == ["api", "sources-page"]:
                payload = backend.sources_page(
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 100),
                )
            elif parts == ["api", "categories"]:
                payload = backend.categories_list()
            elif parts == ["api", "tags"]:
                payload = backend.tags_list()
            elif parts == ["api", "workspaces"]:
                payload = backend.workspaces_list()
            elif parts == ["api", "agents"]:
                payload = backend.agents_list()
            elif parts == ["api", "workflows"]:
                payload = backend.workflow_list(
                    name=_one(query, "name") or None,
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                    include_archived=_one(query, "include_archived") == "1",
                )
            elif parts == ["api", "runs"]:
                payload = backend.run_list(
                    status=_one(query, "status") or None,
                    workflow_id=_one(query, "workflow_id") or None,
                    skill_id=_one(query, "skill_id") or None,
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif parts == ["api", "deployments", "transactions"]:
                payload = backend.deployment_transactions_list(
                    state=_one(query, "state") or None,
                    skill_id=_one(query, "skill_id") or None,
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif parts == ["api", "deployments", "locations"]:
                payload = backend.managed_locations_list(
                    skill_id=_one(query, "skill_id") or None,
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif parts == ["api", "audit"]:
                payload = backend.audit_list(
                    entity_type=_one(query, "entity_type") or None,
                    entity_id=_one(query, "entity_id") or None,
                    action=_one(query, "action") or None,
                    cursor=_int(_one(query, "cursor"), 0),
                    limit=_int(_one(query, "limit"), 50),
                )
            elif len(parts) == 3 and parts[:2] == ["api", "skills"]:
                payload = backend.skill_metadata(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "body":
                payload = backend.skill_body(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "resources":
                payload = backend.skill_resources(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "organization":
                payload = backend.skill_organization_get(parts[2])
            elif len(parts) == 3 and parts[:2] == ["api", "workflows"]:
                payload = backend.workflow_get(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "workflows"] and parts[3] == "usage":
                payload = backend.workflow_usage(parts[2])
            elif len(parts) == 3 and parts[:2] == ["api", "runs"]:
                payload = backend.run_get(parts[2])
            else:
                self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(payload)
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = self._parts(parsed.path)
        backend = self.server.backend
        try:
            body = self._body()
            if len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "validate":
                payload = backend.skill_validate(parts[2], body.get("variant_id"))
            elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "evaluate":
                payload = backend.skill_evaluate(parts[2], str(body.get("query", "")))
            elif len(parts) == 4 and parts[:2] == ["api", "skills"] and parts[3] == "open-folder":
                payload = backend.skill_open_folder(parts[2], body.get("variant_id"))
            elif parts == ["api", "categories"]:
                self._mutation_guard()
                payload = backend.category_upsert(
                    str(body.get("name", "")), str(body.get("description", ""))
                )
            elif parts == ["api", "tags"]:
                self._mutation_guard()
                payload = backend.tag_upsert(str(body.get("name", "")))
            elif len(parts) == 4 and parts[:2] == ["api", "categories"] and parts[3] == "delete":
                self._mutation_guard()
                payload = backend.category_delete(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "tags"] and parts[3] == "delete":
                self._mutation_guard()
                payload = backend.tag_delete(parts[2])
            elif (
                len(parts) == 5
                and parts[:2] == ["api", "skills"]
                and parts[3:] == ["categories", "bind"]
            ):
                self._mutation_guard()
                payload = backend.skill_category_bind(parts[2], str(body.get("category_id", "")))
            elif (
                len(parts) == 5
                and parts[:2] == ["api", "skills"]
                and parts[3:] == ["categories", "unbind"]
            ):
                self._mutation_guard()
                payload = backend.skill_category_unbind(parts[2], str(body.get("category_id", "")))
            elif (
                len(parts) == 5 and parts[:2] == ["api", "skills"] and parts[3:] == ["tags", "bind"]
            ):
                self._mutation_guard()
                payload = backend.skill_tag_bind(parts[2], str(body.get("tag_id", "")))
            elif (
                len(parts) == 5
                and parts[:2] == ["api", "skills"]
                and parts[3:] == ["tags", "unbind"]
            ):
                self._mutation_guard()
                payload = backend.skill_tag_unbind(parts[2], str(body.get("tag_id", "")))
            elif parts == ["api", "workflows", "preview"]:
                payload = backend.workflow_create(body.get("spec", {}), dry_run=True)
            elif parts == ["api", "workflows"]:
                self._mutation_guard()
                payload = backend.workflow_create(body.get("spec", {}))
            elif len(parts) == 4 and parts[:2] == ["api", "workflows"] and parts[3] == "archive":
                self._mutation_guard()
                payload = backend.workflow_archive(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "workflows"] and parts[3] == "restore":
                self._mutation_guard()
                payload = backend.workflow_restore(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "workflows"] and parts[3] == "delete":
                self._mutation_guard()
                if body.get("confirm") is not True:
                    raise ValidationError("workflow-delete-confirm-required")
                payload = backend.workflow_delete(parts[2])
            elif parts == ["api", "workflow-families", "archive"]:
                self._mutation_guard()
                payload = backend.workflow_family_archive(str(body.get("name", "")))
            elif len(parts) == 4 and parts[:2] == ["api", "workflows"] and parts[3] == "plan":
                context = body.get("context")
                if context is not None and not isinstance(context, dict):
                    raise TypeError("context-object-required")
                payload = backend.workflow_plan(parts[2], context)
            elif parts == ["api", "runs"]:
                self._mutation_guard()
                payload = backend.run_create(
                    str(body.get("workflow_id", "")),
                    body.get("context"),
                    body.get("run_key"),
                )
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "start":
                self._mutation_guard()
                payload = backend.run_start(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "block":
                self._mutation_guard()
                payload = backend.run_block(parts[2], str(body.get("reason", "")))
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "evidence":
                self._mutation_guard()
                payload = backend.run_evidence_add(
                    parts[2],
                    str(body.get("kind", "")),
                    body.get("payload", {}),
                    body.get("evidence_key"),
                )
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "resume":
                self._mutation_guard()
                payload = backend.run_resume(parts[2])
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "succeed":
                self._mutation_guard()
                payload = backend.run_succeed(parts[2], body.get("gate_result"))
            elif parts == ["api", "deployments", "plan"]:
                payload = backend.deployment_plan(
                    str(body.get("skill_id", "")),
                    str(body.get("operation", "")),
                    body.get("source_path"),
                    body.get("target_path"),
                )
            else:
                self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(payload)
        except Exception as exc:
            self._error(exc)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8955,
    *,
    registry=None,
    db_path: Path | str = DEFAULT_DB,
    web_root: Path = WEB_ROOT,
    explorer_opener=open_explorer_folder,
) -> ManagerHTTPServer:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("manager-host-must-be-loopback")
    if registry is None:
        active_registry = build_default_registry()
        active_registry.load_existing_index()
    else:
        active_registry = registry
        active_registry.payload()
    backend = ManagerBackend(
        active_registry,
        db_path,
        explorer_opener=explorer_opener,
    )
    return ManagerHTTPServer((host, port), backend, web_root)


def serve(host: str = "127.0.0.1", port: int = 8955) -> None:
    server = create_server(host, port)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill-control-plane-manager")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8955)
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    main()
