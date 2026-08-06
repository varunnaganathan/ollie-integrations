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
    return {
        "interaction_type": "run",
        "name": collector.workflow_name,
        "input": collector.input_text,
        "output": collector.output_text,
        "events": events,
        "_signal_hits": signal_hits,
        "attributes": [
            {"name": "latency_ms", "value": collector.latency_ms},
            {"name": "success", "value": success},
        ],
        "started_at": collector.started_at,
        "ended_at": collector.ended_at or collector.started_at,
    }
