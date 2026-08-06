"""Behavior signals for OpenAI Agents single-run traces."""

from __future__ import annotations

import os
from typing import Any

SAFETY_FINISH = frozenset({"safety", "content_filter", "content_filtered"})
TRUNCATED_FINISH = frozenset({"length", "max_tokens", "max_output_tokens"})


def _span_type(span: dict[str, Any]) -> str:
    return str(span.get("type") or "").strip()


def _span_status(span: dict[str, Any]) -> str:
    return str(span.get("status") or "success").strip()


def _high_latency_ms() -> int:
    try:
        return max(1, int(os.getenv("OLLIE_HIGH_LATENCY_MS", "30000")))
    except ValueError:
        return 30000


def direct_signals(
    *,
    spans: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Framework-direct behavior signals from span fields (P1 / guardrail)."""
    trigger: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []

    for span in spans:
        st = _span_type(span)
        status = _span_status(span)
        if st == "guardrail" and (status == "failure" or span.get("triggered")):
            trigger.append({"name": "guardrail_blocked", "guardrail": span.get("name")})
        elif st == "tool" and status == "failure":
            context.append({"name": "tool_error", "tool": span.get("name")})
        elif st == "llm" and status == "failure":
            context.append({"name": "llm_error", "llm": span.get("name")})
        elif st == "llm":
            fr = str(span.get("finish_reason") or "").strip().lower()
            if fr in TRUNCATED_FINISH:
                context.append({"name": "output_truncated"})
            elif fr in SAFETY_FINISH:
                context.append({"name": "safety_stop"})

    return trigger, _dedupe(context)


def derived_signals(
    *,
    spans: list[dict[str, Any]],
    output: str,
    success: bool,
    latency_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """P2 session-bad outcomes + repeated tool failure pattern."""
    trigger: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []

    if not success:
        context.append({"name": "runtime_failure"})
    if not str(output or "").strip():
        context.append({"name": "empty_final_response"})

    tool_spans = [s for s in spans if _span_type(s) == "tool"]
    failed_tools = [s for s in tool_spans if _span_status(s) == "failure"]
    if len(failed_tools) >= 2:
        trigger.append({"name": "repeated_tool_error"})
    elif len(failed_tools) == 1:
        context.append({"name": "tool_error", "tool": failed_tools[0].get("name")})

    if latency_ms >= _high_latency_ms():
        context.append({"name": "high_latency"})

    return trigger, _dedupe(context)


def instrument_events(
    *,
    spans: list[dict[str, Any]],
    output: str,
    success: bool,
    latency_ms: int,
    interaction_ref: str = "ix_0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build events (spans only; empty trigger/context) and anchored _signal_hits."""
    from ollie_integrations_openai_agents.hits import hits_from_named_signals

    trig_d, ctx_d = direct_signals(spans=spans)
    trig_b, ctx_b = derived_signals(spans=spans, output=output, success=success, latency_ms=latency_ms)
    trigger = _dedupe(trig_d + trig_b)
    context = _dedupe(ctx_d + ctx_b)
    pending = hits_from_named_signals(
        trigger=trigger,
        context=context,
        spans=spans,
        interaction_ref=interaction_ref,
    )
    return (
        {
            "trigger": [],
            "context": [],
            "spans": spans,
        },
        pending,
    )


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
