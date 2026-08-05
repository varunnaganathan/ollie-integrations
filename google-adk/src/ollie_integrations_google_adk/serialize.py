"""Serialize ADK objects to wire-safe strings (no google-adk import required)."""

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


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=_json_default)
    except (TypeError, ValueError):
        return json.dumps({"repr": repr(obj)[:2000]})


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def content_to_input_string(content: Any) -> str:
    """Flatten google.genai.types.Content (or dict) to readable string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts") or []
        role = content.get("role")
    else:
        parts = getattr(content, "parts", None) or []
        role = getattr(content, "role", None)
    lines: list[str] = []
    if role:
        lines.append(f"role={role}")
    for part in parts:
        lines.extend(_part_lines(part))
    return "\n".join(lines).strip() or safe_json(content)


def _part_lines(part: Any) -> list[str]:
    if isinstance(part, dict):
        if part.get("text"):
            return [str(part["text"])]
        if part.get("function_call"):
            fc = part["function_call"]
            if isinstance(fc, dict):
                return [f"function_call: {fc.get('name')}({safe_json(fc.get('args', {}))})"]
            return [f"function_call: {safe_json(fc)}"]
        if part.get("function_response"):
            fr = part["function_response"]
            if isinstance(fr, dict):
                return [f"function_response: {fr.get('name')} -> {safe_json(fr.get('response', {}))}"]
            return [f"function_response: {safe_json(fr)}"]
        return [safe_json(part)]
    text = getattr(part, "text", None)
    if text:
        return [str(text)]
    fc = getattr(part, "function_call", None)
    if fc is not None:
        name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else "?")
        args = getattr(fc, "args", None) or (fc.get("args") if isinstance(fc, dict) else {})
        return [f"function_call: {name}({safe_json(args)})"]
    fr = getattr(part, "function_response", None)
    if fr is not None:
        name = getattr(fr, "name", None) or (fr.get("name") if isinstance(fr, dict) else "?")
        resp = getattr(fr, "response", None) or (fr.get("response") if isinstance(fr, dict) else {})
        return [f"function_response: {name} -> {safe_json(resp)}"]
    return [safe_json(part)]


def event_text(event: Any) -> str | None:
    """Extract assistant/user text from an ADK Event."""
    if event is None:
        return None
    content = getattr(event, "content", None) if not isinstance(event, dict) else event.get("content")
    if content is None:
        return None
    text = content_to_input_string(content)
    return text or None


def session_messages_for_invocation(
    session: Any,
    invocation_id: str,
    *,
    branch: str | None = None,
    author: str | None = None,
) -> str:
    events = getattr(session, "events", None) or []
    lines: list[str] = []
    for ev in events:
        inv = getattr(ev, "invocation_id", None) or (ev.get("invocation_id") if isinstance(ev, dict) else None)
        if inv and str(inv) != str(invocation_id):
            continue
        ev_branch = getattr(ev, "branch", None) if not isinstance(ev, dict) else ev.get("branch")
        if branch is not None and ev_branch is not None and str(ev_branch) != str(branch):
            continue
        ev_author = getattr(ev, "author", None) if not isinstance(ev, dict) else ev.get("author")
        if author is not None and ev_author is not None and str(ev_author) != str(author):
            continue
        partial = getattr(ev, "partial", False) if not isinstance(ev, dict) else ev.get("partial", False)
        if partial:
            continue
        text = event_text(ev)
        if text:
            label = ev_author or "event"
            lines.append(f"{label}: {text}")
    return "\n".join(lines).strip()


def final_model_text(
    session: Any,
    invocation_id: str,
    *,
    author: str | None = None,
) -> str | None:
    events = getattr(session, "events", None) or []
    last: str | None = None
    for ev in events:
        inv = getattr(ev, "invocation_id", None) or (ev.get("invocation_id") if isinstance(ev, dict) else None)
        if inv and str(inv) != str(invocation_id):
            continue
        ev_author = getattr(ev, "author", None) if not isinstance(ev, dict) else ev.get("author")
        if author is not None and ev_author is not None and str(ev_author) != str(author):
            if ev_author == "user":
                continue
            if str(ev_author) != str(author):
                continue
        partial = getattr(ev, "partial", False) if not isinstance(ev, dict) else ev.get("partial", False)
        if partial:
            continue
        if ev_author in (None, "user"):
            continue
        text = event_text(ev)
        if text:
            last = text
    return last


def llm_request_input(llm_request: Any) -> str:
    if llm_request is None:
        return ""
    model = getattr(llm_request, "model", None) or (
        llm_request.get("model") if isinstance(llm_request, dict) else None
    )
    contents = getattr(llm_request, "contents", None) or (
        llm_request.get("contents") if isinstance(llm_request, dict) else None
    ) or []
    lines = [f"model: {model or 'unknown'}"]
    for c in contents:
        lines.append(content_to_input_string(c))
    config = getattr(llm_request, "config", None)
    if config is not None:
        top_p = getattr(config, "top_p", None)
        max_tokens = getattr(config, "max_output_tokens", None)
        if top_p is not None:
            lines.append(f"top_p: {top_p}")
        if max_tokens is not None:
            lines.append(f"max_output_tokens: {max_tokens}")
    return "\n".join(lines).strip()


def llm_response_output(llm_response: Any) -> str:
    if llm_response is None:
        return ""
    content = getattr(llm_response, "content", None)
    if content is not None:
        text = content_to_input_string(content)
        if text:
            return text
    if hasattr(llm_response, "model_dump"):
        try:
            return safe_json(llm_response.model_dump(exclude_none=True))
        except Exception:
            pass
    return safe_json(llm_response)
