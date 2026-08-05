"""Derived behavior signals from span patterns and run outcome."""

from __future__ import annotations

import os
from typing import Any


def _span_type(span: dict[str, Any]) -> str:
    return str(span.get("type") or "").strip()


def _span_status(span: dict[str, Any]) -> str:
    return str(span.get("status") or "success").strip()


def _tool_loop_threshold() -> int:
    try:
        return max(2, int(os.getenv("OLLIE_TOOL_LOOP_THRESHOLD", "5")))
    except ValueError:
        return 5


def _high_latency_ms() -> int:
    try:
        return max(1, int(os.getenv("OLLIE_HIGH_LATENCY_MS", "30000")))
    except ValueError:
        return 30000


def baseline_signals(
    *,
    interaction_type: str,
    spans: list[dict[str, Any]],
    output: str | None = None,
    success: bool = True,
    latency_ms: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (trigger, context) derived signals for one run interaction."""
    _ = interaction_type
    return derived_signals(
        spans=spans,
        output=output or "",
        success=success,
        latency_ms=latency_ms,
    )


def derived_signals(
    *,
    spans: list[dict[str, Any]],
    output: str,
    success: bool,
    latency_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Derived behavior signals from span patterns and run outcome."""
    trigger: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []

    if not success:
        context.append({"name": "runtime_failure"})
    if not str(output or "").strip():
        context.append({"name": "empty_final_response"})

    tool_spans = [s for s in spans if _span_type(s) == "tool"]
    failed_tools = [s for s in tool_spans if _span_status(s) == "failure"]
    if len(failed_tools) >= 2:
        trigger.append({"name": "repeated_tool_error", "tool": failed_tools[0].get("name")})
    elif len(failed_tools) == 1:
        # Ensure tool_error is present even if direct_signals missed it
        context.append({"name": "tool_error", "tool": failed_tools[0].get("name")})

    if len(tool_spans) >= _tool_loop_threshold():
        last = tool_spans[-1]
        context.append({"name": "tool_loop", "tool": last.get("name")})
    if latency_ms >= _high_latency_ms():
        context.append({"name": "high_latency"})

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
