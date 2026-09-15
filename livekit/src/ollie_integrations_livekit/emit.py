"""Build Ollie v2 wire payload from LiveKit execution span collector."""

from __future__ import annotations

from typing import Any

from ollie_integrations_livekit.collector import ExecutionSpanCollector
from ollie_integrations_livekit.normalize import normalize_collector, session_workflow_fields
from ollie_integrations_livekit.version import __version__


def collector_to_wire_payload(
    collector: ExecutionSpanCollector,
    *,
    agent_id: str,
    session_id: str | None = None,
    sdk_name: str = "ollie-integrations-livekit",
) -> dict[str, Any]:
    nodes = collector.nodes_in_order()
    if not nodes:
        raise ValueError("collector has no nodes")

    wf = session_workflow_fields(collector)
    interactions = normalize_collector(collector)
    # Carry session lifecycle onto the first turn so shape audit / inventories can see it.
    if interactions and wf.get("session_events"):
        first = interactions[0]
        events = first.get("events") if isinstance(first.get("events"), dict) else {}
        context = list(events.get("context") or [])
        for ev in wf["session_events"]:
            if isinstance(ev, dict) and str(ev.get("name") or "").startswith("livekit.session"):
                context.append(ev)
        events = {
            "trigger": list(events.get("trigger") or []),
            "context": context,
            "spans": list(events.get("spans") or []),
        }
        first["events"] = events
        # Merge session attrs (room, participant, …) onto first turn without clobbering.
        existing = {str(a.get("name")) for a in (first.get("attributes") or []) if isinstance(a, dict)}
        merged = list(first.get("attributes") or [])
        for a in wf.get("attributes") or []:
            if isinstance(a, dict) and str(a.get("name") or "") not in existing:
                merged.append(a)
                existing.add(str(a.get("name")))
        first["attributes"] = merged

    sid = session_id or collector.session_id or agent_id
    return {
        "schema_version": 2,
        "sdk": {"name": sdk_name, "version": __version__},
        "agent_id": agent_id,
        "session_id": sid,
        "workflow": {
            "name": wf["name"],
            "status": wf["status"],
            "started_at": wf["started_at"],
            "ended_at": wf["ended_at"],
        },
        "interactions": interactions,
    }


def flush_collector_to_client(
    collector: ExecutionSpanCollector,
    client: Any,
    *,
    flush_mode: str = "ingest",
) -> dict[str, Any]:
    payload = collector_to_wire_payload(collector, agent_id=client.agent_id, session_id=collector.session_id)
    mode = str(flush_mode or "ingest").strip().lower()
    if mode == "validate":
        return client._transport.validate_trace(payload, client._delivery)
    if mode == "process":
        return client._transport.process_trace(payload, client._delivery)
    return client._transport.ingest_trace(payload, client._delivery)
