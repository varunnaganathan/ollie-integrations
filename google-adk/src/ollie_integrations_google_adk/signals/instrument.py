"""Orchestrate direct + derived signals for one normalized interaction."""

from __future__ import annotations

from typing import Any

from ollie_integrations_google_adk.signals.baselines import baseline_signals
from ollie_integrations_google_adk.signals.direct import direct_signals, _dedupe
from ollie_integrations_google_adk.signals.hits import hits_from_named_signals


def instrument_interaction(
    *,
    interaction_type: str,
    spans: list[dict[str, Any]],
    output: str | None,
    success: bool,
    latency_ms: int = 0,
    interaction_ref: str = "ix_0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build events (spans only; empty trigger/context) and anchored _signal_hits."""
    trig_direct, ctx_direct = direct_signals(
        interaction_type=interaction_type,
        spans=spans,
        output=output,
        success=success,
    )
    trig_base, ctx_base = baseline_signals(
        interaction_type=interaction_type,
        spans=spans,
        output=output,
        success=success,
        latency_ms=latency_ms,
    )
    trigger = _dedupe(trig_direct + trig_base)
    context = _dedupe(ctx_direct + ctx_base)
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
