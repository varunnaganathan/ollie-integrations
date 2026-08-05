"""Direct/context signals derived from normalized spans and interaction fields."""

from __future__ import annotations

from typing import Any

SAFETY_FINISH = frozenset({"safety", "content_filter", "content_filtered"})
TRUNCATED_FINISH = frozenset({"length", "max_tokens", "max_output_tokens"})
MALFORMED_FINISH = frozenset(
    {
        "malformed_function_call",
        "malformed_function_call_error",
        "invalid_function_call",
    }
)
RATE_LIMIT_CODES = frozenset({"resource_exhausted", "rate_limit", "rate_limited", "429"})
UNAVAILABLE_CODES = frozenset(
    {"unavailable", "deadline_exceeded", "service_unavailable", "503", "504"}
)

_UNKNOWN_TOOL_MARKERS = (
    "not found",
    "unknown tool",
    "no tool named",
    "unregistered",
    "tool does not exist",
    "no such tool",
)


def _span_type(span: dict[str, Any]) -> str:
    return str(span.get("type") or "").strip()


def _span_status(span: dict[str, Any]) -> str:
    return str(span.get("status") or "success").strip()


def _finish_reason(span: dict[str, Any]) -> str:
    fr = span.get("finish_reason")
    if fr is None and isinstance(span.get("properties"), dict):
        fr = span["properties"].get("finish_reason")
    return str(fr or "").strip().lower()


def _error_code(span: dict[str, Any]) -> str:
    code = span.get("error_code")
    if code is None and isinstance(span.get("properties"), dict):
        code = span["properties"].get("error_code")
    return str(code or "").strip().lower()


def _tool_output_text(span: dict[str, Any]) -> str:
    out = span.get("output")
    if isinstance(out, dict):
        return str(out.get("text") or out.get("error") or out).lower()
    return str(out or "").lower()


def is_unknown_tool_failure(span: dict[str, Any]) -> bool:
    """Classify a failed tool span as missing/unregistered tool."""
    err = str(span.get("error_type") or "").strip().lower()
    if "notfound" in err.replace("_", "") or err in ("keyerror", "lookuperror"):
        return True
    text = _tool_output_text(span)
    err_blob = f"{err} {text}"
    return any(m in err_blob for m in _UNKNOWN_TOOL_MARKERS)


def direct_signals(
    *,
    interaction_type: str,
    spans: list[dict[str, Any]],
    output: str | None,
    success: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (trigger, context) direct signals for one interaction."""
    _ = interaction_type
    _ = output
    _ = success
    trigger: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []

    for span in spans:
        st = _span_type(span)
        status = _span_status(span)
        if st == "tool" and status == "failure":
            context.append({"name": "tool_error", "tool": span.get("name")})
            if is_unknown_tool_failure(span):
                context.append({"name": "unknown_tool", "tool": span.get("name")})
        elif st == "llm":
            fr = _finish_reason(span)
            code = _error_code(span)
            if status == "failure" or code in RATE_LIMIT_CODES or code in UNAVAILABLE_CODES:
                if status == "failure" or code:
                    context.append({"name": "llm_error", "llm": span.get("name")})
            if fr in TRUNCATED_FINISH:
                context.append({"name": "output_truncated", "llm": span.get("name")})
            elif fr in SAFETY_FINISH:
                context.append({"name": "safety_stop", "llm": span.get("name")})
            elif fr in MALFORMED_FINISH:
                context.append({"name": "malformed_tool_call", "llm": span.get("name")})
            if code in RATE_LIMIT_CODES:
                context.append({"name": "rate_limited", "llm": span.get("name")})
            elif code in UNAVAILABLE_CODES:
                context.append({"name": "provider_unavailable", "llm": span.get("name")})

    return trigger, _dedupe(context)


def _dedupe(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for sig in signals:
        name = str(sig.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(sig)
    return out
