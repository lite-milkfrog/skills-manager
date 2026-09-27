from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_id(prefix: str, *parts: object) -> str:
    material = "\0".join(str(part).casefold() for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:20]}"


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def json_value(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def condition_matches(condition: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    field = condition.get("field")
    if not isinstance(field, str) or not field:
        return False
    current: Any = context
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            current = None
            break
        current = current[part]
    if "equals" in condition:
        return current == condition["equals"]
    if "not_equals" in condition:
        return current != condition["not_equals"]
    if "in" in condition and isinstance(condition["in"], list):
        return current in condition["in"]
    if "exists" in condition:
        return (current is not None) is bool(condition["exists"])
    return bool(current)
