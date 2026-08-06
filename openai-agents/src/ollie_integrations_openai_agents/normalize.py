"""Normalize RunCollector to single run interaction."""

from __future__ import annotations

from typing import Any

from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.signals import instrument_events
from ollie_integrations_openai_agents.warehouse_span import warehouse_shape_spans


def normalize_collector(collector: RunCollector) -> dict[str, Any]:
    """Return one run interaction dict (not yet wire-finalized)."""
    success = collector.status != "failed"
    spans = warehouse_shape_spans(list(collector.spans))
    events, signal_hits = instrument_events(
        spans=spans,
        output=collector.output_text,
        success=success,
        latency_ms=collector.latency_ms,
        interaction_ref="ix_0",
    )
    # Union auto + user emits (dedupe by signal|kind|anchor).
    pending = list(signal_hits)
    seen = {
        (
            str(h.get("signal") or ""),
            str(h.get("kind") or ""),
            str(h.get("anchor_kind") or ""),
            str(h.get("anchor_id") or ""),
        )
        for h in pending
        if isinstance(h, dict)
    }
    for h in collector.user_signal_hits:
        if not isinstance(h, dict):
            continue
        key = (
            str(h.get("signal") or ""),
            str(h.get("kind") or ""),
            str(h.get("anchor_kind") or ""),
            str(h.get("anchor_id") or ""),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        pending.append(h)

    attributes: list[dict[str, Any]] = [
        {"name": "latency_ms", "value": collector.latency_ms},
        {"name": "success", "value": success},
    ]
    for name, value in collector.run_attributes.items():
        key = str(name or "").strip()
        if not key or key in ("latency_ms", "success"):
            continue
        attributes.append({"name": key, "value": value})
    return {
        "interaction_type": "run",
        "name": collector.workflow_name,
        "input": collector.input_text,
        "output": collector.output_text,
        "events": events,
        "_signal_hits": pending,
        "attributes": attributes,
        "started_at": collector.started_at,
        "ended_at": collector.ended_at or collector.started_at,
    }
