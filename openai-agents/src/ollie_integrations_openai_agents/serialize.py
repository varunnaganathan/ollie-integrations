"""Serialize values to wire-safe strings."""

from __future__ import annotations

import json
from typing import Any

MAX_WIRE_CHARS = 32_000


def truncate(text: str | None, *, max_chars: int = MAX_WIRE_CHARS) -> tuple[str, bool]:
    if text is None:
        return "", False
    s = str(text)
    if len(s) <= max_chars:
        return s, False
    return s[:max_chars] + "…[truncated]", True


def to_input_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return safe_json(value)


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=_json_default)
    except (TypeError, ValueError):
        return json.dumps({"repr": repr(obj)[:2000]})


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if hasattr(obj, "to_dict"):
        return obj.model_dump() if hasattr(obj, "model_dump") else obj.to_dict()
    return str(obj)
