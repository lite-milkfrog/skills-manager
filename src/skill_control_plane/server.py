from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .core import Registry, build_default_registry, validate_skill_file
from .deployment import DeploymentPolicyError, DeploymentService
from .management import ValidationError
from .manager import ManagerBackend, ManagerError
from .registry_store import RegistryStore
from .run_state import RunService, TransitionError
from .storage import ControlPlaneDB
from .workflow import WorkflowService

SERVER_VERSION = "0.3.0"
DEFAULT_DB = Path(__file__).resolve().parents[2] / "runtime" / "state" / "control-plane.db"
DEFAULT_MANAGED_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "m04-managed"
DEFAULT_PROTECTED_ROOTS = (
    Path(__file__).resolve().parents[2] / ".." / "webgpt-as-codex",
    Path(__file__).resolve().parents[2] / ".." / ".skills",
)


def _tool_result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "skills_status",
            "description": (
                "Return local Skills registry status and explicit source-authority policy."
            ),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "skills_list",
            "description": "List selected skills as compact metadata records.",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_search",
            "description": "Search selected local skills by task, keywords, description, or path.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_get",
            "description": (
                "Load one complete selected SKILL.md plus preserved source variants on demand."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_resources",
            "description": (
                "Read the bounded internal text resources for one selected Skill directory "
                "(references, routes, workflows, scripts, and similar files) on demand. "
                "This does not scan or upload the whole Skills registry."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_resolve",
            "description": (
                "Resolve a Skill as a recursive capability entry point: load the complete "
                "canonical SKILL.md, follow explicitly referenced internal resources, and "
                "recursively load explicitly named canonical child Skills within strict bounds. "
                "Use this before executing Router or Composite Skills."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "task": {"type": "string"},
                    "max_depth": {"type": "integer", "minimum": 0, "maximum": 4},
                    "max_skills": {"type": "integer", "minimum": 1, "maximum": 24},
                    "max_total_bytes": {
                        "type": "integer",
                        "minimum": 65536,
                        "maximum": 2097152,
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_validate",
            "description": "Validate a SKILL.md by canonical skill name or explicit local path.",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "path": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "skills_evaluate",
            "description": "Evaluate whether a selected skill ranks for a task query.",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "query": {"type": "string"}},
                "required": ["name", "query"],
                "additionalProperties": False,
            },
        },
    ]


def headless_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "workflow_list",
            "description": "List stored active Workflows as compact metadata.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cursor": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "workflow_search",
            "description": (
                "Search Workflows by name, description, stage labels, binding labels, "
                "and bound Skill names."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "cursor": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "workflow_get",
            "description": "Return one stored Workflow with ordered stages and Skill bindings.",
            "inputSchema": {
                "type": "object",
                "properties": {"workflow_id": {"type": "string"}},
                "required": ["workflow_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "workflow_create",
            "description": (
                "Create a versioned semantic workflow. Each stage may describe its own title, "
                "purpose, Agent instructions, expected output, and completion criteria, with "
                "optional canonical Skill bindings."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "spec": {"type": "object"},
                    "dry_run": {"type": "boolean"},
                },
                "required": ["spec"],
                "additionalProperties": False,
            },
        },
        {
            "name": "workflow_plan",
            "description": "Resolve a stored workflow into a deterministic execution plan.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["workflow_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "workflow_prompt",
            "description": (
                "Generate an Agent-ready recursive execution prompt for a stored Workflow "
                "without flattening Router or Composite Skills."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["workflow_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_create",
            "description": "Create a durable planned workflow run.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string"},
                    "context": {"type": "object"},
                    "run_key": {"type": "string"},
                },
                "required": ["workflow_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_get",
            "description": "Return a durable run snapshot including evidence and audit history.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_start",
            "description": "Start a planned durable run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_block",
            "description": "Block the current run stage with an explicit reason.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["run_id", "reason"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_evidence_add",
            "description": "Persist evidence against the current durable run stage.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "payload": {"type": "object"},
                    "evidence_key": {"type": "string"},
                },
                "required": ["run_id", "kind", "payload"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_resume",
            "description": "Resume a blocked run after durable evidence exists.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_succeed",
            "description": "Mark the current running stage successful and advance legally.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "gate_result": {"type": "object"},
                },
                "required": ["run_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "deployment_plan",
            "description": (
                "Create a deterministic M03 deployment dry-run plan only; no physical apply."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string"},
                    "operation": {"type": "string"},
                    "source_path": {"type": "string"},
                    "target_path": {"type": "string"},
                },
                "required": ["skill_id", "operation"],
                "additionalProperties": False,
            },
        },
    ]


def call_tool(
    registry: Registry,
    name: str,
    arguments: dict[str, Any],
    *,
    db: ControlPlaneDB | None = None,
) -> dict[str, Any]:
    try:
        if name == "skills_status":
            return _tool_result(registry.status())
        if name == "skills_list":
            limit = int(arguments.get("limit", 100))
            rows = registry.records()[: max(1, min(limit, 200))]
            compact = [
                {
                    "skill_id": row["skill_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "path": row["path"],
                    "source_class": row["source_class"],
                    "authority_tier": row["authority_tier"],
                    "category_router": row["category_router"],
                }
                for row in rows
            ]
            return _tool_result(compact)
        if name == "skills_search":
            return _tool_result(
                registry.search(
                    str(arguments.get("query", "")),
                    int(arguments.get("limit", 20)),
                )
            )
        if name == "skills_get":
            return _tool_result(registry.get(str(arguments.get("name", ""))))
        if name == "skills_resources":
            manager = ManagerBackend(registry, DEFAULT_DB)
            return _tool_result(manager.skill_resources(str(arguments.get("name", ""))))
        if name == "skills_resolve":
            manager = ManagerBackend(registry, DEFAULT_DB)
            return _tool_result(
                manager.skill_resolve(
                    str(arguments.get("name", "")),
                    task=str(arguments.get("task", "")),
                    max_depth=int(arguments.get("max_depth", 2)),
                    max_skills=int(arguments.get("max_skills", 12)),
                    max_total_bytes=int(arguments.get("max_total_bytes", 512 * 1024)),
                )
            )
        if name == "skills_validate":
            explicit = arguments.get("path")
            if explicit:
                return _tool_result(validate_skill_file(Path(str(explicit))))
            row = registry.find(str(arguments.get("name", "")))
            if row is None:
                raise KeyError(str(arguments.get("name", "")))
            return _tool_result(validate_skill_file(Path(str(row["path"]))))
        if name == "skills_evaluate":
            return _tool_result(
                registry.evaluate(
                    str(arguments.get("name", "")),
                    str(arguments.get("query", "")),
                )
            )
        if db is None:
            return _tool_result(
                {"error": "headless-state-unavailable", "name": name},
                is_error=True,
            )
        workflows = WorkflowService(db)
        runs = RunService(db)
        if name == "workflow_list":
            return _tool_result(
                workflows.list_workflows(
                    cursor=int(arguments.get("cursor", 0)),
                    limit=int(arguments.get("limit", 50)),
                )
            )
        if name == "workflow_search":
            return _tool_result(
                workflows.search_workflows(
                    str(arguments.get("query", "")),
                    cursor=int(arguments.get("cursor", 0)),
                    limit=int(arguments.get("limit", 50)),
                )
            )
        if name == "workflow_get":
            return _tool_result(workflows.get_workflow(str(arguments.get("workflow_id", ""))))
        if name == "workflow_create":
            spec = arguments.get("spec")
            if not isinstance(spec, dict):
                raise TypeError("spec")
            return _tool_result(
                workflows.create_workflow(spec, dry_run=bool(arguments.get("dry_run", False)))
            )
        if name == "workflow_plan":
            context = arguments.get("context")
            if context is not None and not isinstance(context, dict):
                raise TypeError("context")
            return _tool_result(workflows.plan(str(arguments.get("workflow_id", "")), context))
        if name == "workflow_prompt":
            context = arguments.get("context")
            if context is not None and not isinstance(context, dict):
                raise TypeError("context")
            return _tool_result(workflows.prompt(str(arguments.get("workflow_id", "")), context))
        if name == "run_create":
            context = arguments.get("context")
            if context is not None and not isinstance(context, dict):
                raise TypeError("context")
            return _tool_result(
                runs.create_run(
                    str(arguments.get("workflow_id", "")),
                    context,
                    run_key=(str(arguments["run_key"]) if arguments.get("run_key") else None),
                )
            )
        if name == "run_get":
            return _tool_result(runs.snapshot(str(arguments.get("run_id", ""))))
        if name == "run_start":
            return _tool_result(runs.start(str(arguments.get("run_id", ""))))
        if name == "run_block":
            return _tool_result(
                runs.block(
                    str(arguments.get("run_id", "")),
                    str(arguments.get("reason", "")),
                )
            )
        if name == "run_evidence_add":
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                raise TypeError("payload")
            return _tool_result(
                runs.add_evidence(
                    str(arguments.get("run_id", "")),
                    str(arguments.get("kind", "")),
                    payload,
                    evidence_key=(
                        str(arguments["evidence_key"]) if arguments.get("evidence_key") else None
                    ),
                )
            )
        if name == "run_resume":
            return _tool_result(runs.resume(str(arguments.get("run_id", ""))))
        if name == "run_succeed":
            gate = arguments.get("gate_result")
            if gate is not None and not isinstance(gate, dict):
                raise TypeError("gate_result")
            return _tool_result(runs.succeed_current(str(arguments.get("run_id", "")), gate))
        if name == "deployment_plan":
            deployment = DeploymentService(
                db,
                protected_roots=DEFAULT_PROTECTED_ROOTS,
                managed_roots=(DEFAULT_MANAGED_ROOT,),
            )
            return _tool_result(
                deployment.plan(
                    str(arguments.get("skill_id", "")),
                    str(arguments.get("operation", "")),
                    source_path=arguments.get("source_path"),
                    target_path=arguments.get("target_path"),
                )
            )
        return _tool_result({"error": "unknown-tool", "name": name}, is_error=True)
    except (
        DeploymentPolicyError,
        KeyError,
        ManagerError,
        OSError,
        TransitionError,
        UnicodeError,
        ValidationError,
        ValueError,
        TypeError,
    ) as exc:
        return _tool_result({"error": type(exc).__name__, "detail": str(exc)}, is_error=True)


class SkillsHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        registry: Registry,
        db_path: Path,
    ) -> None:
        self.registry = registry
        self.db_path = db_path
        super().__init__(address, SkillsRequestHandler)


class SkillsRequestHandler(BaseHTTPRequestHandler):
    server: SkillsHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(self.server.registry.status())
            return
        self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/mcp":
            self._json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("invalid-body-size")
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "parse error"}},
                HTTPStatus.BAD_REQUEST,
            )
            return
        if not isinstance(request, dict):
            self._json(
                {"jsonrpc": "2.0", "error": {"code": -32600, "message": "invalid request"}},
                HTTPStatus.BAD_REQUEST,
            )
            return

        method = request.get("method")
        request_id = request.get("id")
        if method == "notifications/initialized":
            self.send_response(HTTPStatus.ACCEPTED.value)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if method == "initialize":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            version = str(params.get("protocolVersion") or "2025-06-18")
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "skill-control-plane", "version": SERVER_VERSION},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tools_schema() + headless_tools_schema()}
        elif method == "tools/call":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            tool_name = str(params.get("name", ""))
            if tool_name.startswith("skills_"):
                result = call_tool(self.server.registry, tool_name, arguments)
            else:
                with ControlPlaneDB(self.server.db_path) as db:
                    result = call_tool(
                        self.server.registry,
                        tool_name,
                        arguments,
                        db=db,
                    )
        else:
            self._json(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "method not found"},
                }
            )
            return
        self._json({"jsonrpc": "2.0", "id": request_id, "result": result})


def serve(
    registry: Registry,
    host: str,
    port: int,
    *,
    db_path: Path | str = DEFAULT_DB,
) -> None:
    registry.payload(force=True)
    canonical_db_path = Path(db_path)
    with ControlPlaneDB(canonical_db_path) as db:
        db.migrate()
    server = SkillsHTTPServer((host, port), registry, canonical_db_path)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill-control-plane")
    sub = parser.add_subparsers(dest="action", required=True)

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8943)

    sub.add_parser("reindex")
    sub.add_parser("status")
    reconcile_parser = sub.add_parser("state-reconcile")
    reconcile_parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[2] / "runtime" / "state" / "control-plane.db"),
    )
    state_status_parser = sub.add_parser("state-status")
    state_status_parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[2] / "runtime" / "state" / "control-plane.db"),
    )
    get_parser = sub.add_parser("get")
    get_parser.add_argument("name")

    args = parser.parse_args(argv)
    registry = build_default_registry()
    if args.action == "serve":
        serve(registry, args.host, args.port)
        return 0
    if args.action == "reindex":
        payload = registry.payload(force=True)
    elif args.action == "state-reconcile":
        snapshot = registry.payload(force=True)
        with ControlPlaneDB(Path(args.db)) as db:
            store = RegistryStore(db)
            reconcile = store.reconcile(
                snapshot,
                legacy_config_path=registry.legacy_config_path,
            )
            payload = {
                "reconcile": reconcile,
                "parity": store.parity(snapshot),
                "integrity": db.integrity(),
            }
    elif args.action == "state-status":
        snapshot = registry.payload(force=True)
        with ControlPlaneDB(Path(args.db)) as db:
            store = RegistryStore(db)
            payload = {
                "parity": store.parity(snapshot),
                "integrity": db.integrity(),
            }
    elif args.action == "status":
        payload = registry.status()
    elif args.action == "get":
        payload = registry.get(args.name)
    else:
        raise AssertionError(args.action)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
