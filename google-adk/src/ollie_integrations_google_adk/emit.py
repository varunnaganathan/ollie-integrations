"""Build Ollie v2 wire payload from execution span collector."""

from __future__ import annotations

from typing import Any

from ollie_integrations_google_adk.collector import ExecutionSpanCollector, utc_now_iso
from ollie_integrations_google_adk.models import ExecutionType
from ollie_integrations_google_adk.normalize import normalize_collector
from ollie_integrations_google_adk.serialize import truncate
from ollie_integrations_google_adk.signals.hits import make_signal_hit
from ollie_integrations_google_adk.version import __version__


def collector_to_wire_payload(
    collector: ExecutionSpanCollector,
    *,
    agent_id: str,
    session_id: str | None = None,
    sdk_name: str = "ollie-integrations-google-adk",
) -> dict[str, Any]:
    nodes = collector.nodes_in_order()
    if not nodes:
        raise ValueError("collector has no nodes")

    raw_interactions = normalize_collector(collector)
    interactions: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_interactions):
        interactions.append(_finalize_interaction(raw, interaction_ref=f"ix_{i}", parent_ref=None if i == 0 else "ix_0"))

    workflow_node = next(n for n in nodes if n.execution_type == ExecutionType.WORKFLOW)
    sid = session_id or collector.session_id or agent_id
    return {
        "schema_version": 2,
        "sdk": {"name": sdk_name, "version": __version__},
        "agent_id": agent_id,
        "session_id": sid,
        "workflow": {
            "name": collector.app_name,
            "status": collector.status,
            "started_at": workflow_node.started_at,
            "ended_at": workflow_node.ended_at or utc_now_iso(),
        },
        "interactions": interactions,
    }


def _finalize_interaction(
    raw: dict[str, Any],
    *,
    interaction_ref: str,
    parent_ref: str | None,
) -> dict[str, Any]:
    inp, inp_trunc = truncate(raw.get("input"))
    out_raw = raw.get("output")
    out, out_trunc = truncate(out_raw if out_raw is not None else None)

    events = dict(raw.get("events") or {"trigger": [], "context": [], "spans": []})
    events["trigger"] = []
    events["context"] = []

    pending = list(raw.get("_signal_hits") or [])
    # Remap interaction anchors to this interaction_ref; keep span anchors as span_ref.
    remapped: list[dict[str, Any]] = []
    for hit in pending:
        if not isinstance(hit, dict):
            continue
        h = dict(hit)
        if str(h.get("anchor_kind") or "") == "interaction":
            h["anchor_id"] = interaction_ref
        remapped.append(h)
    # Wire I/O truncation is not a product signal; llm finish_reason drives output_truncated.
    _ = inp_trunc
    _ = out_trunc

    wire: dict[str, Any] = {
        "interaction_ref": interaction_ref,
        "parent_interaction_ref": parent_ref,
        "interaction_type": raw.get("interaction_type"),
        "name": raw.get("name"),
        "input": inp,
        "output": out if out_raw is not None else None,
        "events": events,
        "_signal_hits": remapped,
        "attributes": list(raw.get("attributes") or []),
        "started_at": raw.get("started_at"),
        "ended_at": raw.get("ended_at"),
    }
    return wire


def flush_collector_to_client(
    collector: ExecutionSpanCollector,
    client: Any,
    *,
    flush_mode: str = "ingest",
) -> dict[str, Any]:
    payload = collector_to_wire_payload(
        collector,
        agent_id=client.agent_id,
        session_id=collector.session_id,
    )
    mode = str(flush_mode or "ingest").strip().lower()
    if mode == "validate":
        return client._transport.validate_trace(payload, client._delivery)
    if mode == "process":
        return client._transport.process_trace(payload, client._delivery)
    return client._transport.ingest_trace(payload, client._delivery)
