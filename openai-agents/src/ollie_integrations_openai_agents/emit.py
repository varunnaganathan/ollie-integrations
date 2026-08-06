"""Build Ollie v2 wire payload from RunCollector."""

from __future__ import annotations

from typing import Any

from ollie_integrations_openai_agents.collector import RunCollector, utc_now_iso
from ollie_integrations_openai_agents.hits import make_signal_hit
from ollie_integrations_openai_agents.normalize import normalize_collector
from ollie_integrations_openai_agents.serialize import truncate
from ollie_integrations_openai_agents.version import __version__


def collector_to_wire_payload(
    collector: RunCollector,
    *,
    agent_id: str,
    session_id: str | None = None,
    sdk_name: str = "ollie-integrations-openai-agents",
) -> dict[str, Any]:
    raw = normalize_collector(collector)
    interaction = _finalize_interaction(raw, interaction_ref="ix_0")
    sid = session_id or collector.session_id or agent_id
    return {
        "schema_version": 2,
        "sdk": {"name": sdk_name, "version": __version__},
        "agent_id": agent_id,
        "session_id": sid,
        "workflow": {
            "name": collector.workflow_name,
            "status": collector.status,
            "started_at": collector.started_at,
            "ended_at": collector.ended_at or utc_now_iso(),
        },
        "interactions": [interaction],
    }


def _finalize_interaction(raw: dict[str, Any], *, interaction_ref: str) -> dict[str, Any]:
    inp, inp_trunc = truncate(raw.get("input"))
    out_raw = raw.get("output")
    out, out_trunc = truncate(out_raw if out_raw is not None else None)

    events = dict(raw.get("events") or {"trigger": [], "context": [], "spans": []})
    events["trigger"] = []
    events["context"] = []

    pending = list(raw.get("_signal_hits") or [])
    seen = {str(h.get("signal") or "") for h in pending if isinstance(h, dict)}
    if inp_trunc and "input_truncated" not in seen:
        pending.append(
            make_signal_hit(
                signal="input_truncated",
                kind="context",
                anchor_kind="interaction",
                anchor_id=interaction_ref,
            )
        )
    if out_trunc and "output_truncated" not in seen:
        pending.append(
            make_signal_hit(
                signal="output_truncated",
                kind="context",
                anchor_kind="interaction",
                anchor_id=interaction_ref,
            )
        )

    if not inp.strip() and not (out or "").strip():
        raise ValueError("interaction requires at least one non-empty input or output string")

    return {
        "interaction_ref": interaction_ref,
        "parent_interaction_ref": None,
        "interaction_type": raw.get("interaction_type"),
        "name": raw.get("name"),
        "input": inp,
        "output": out if out_raw is not None else "",
        "events": events,
        "_signal_hits": pending,
        "attributes": list(raw.get("attributes") or []),
        "started_at": raw.get("started_at"),
        "ended_at": raw.get("ended_at"),
    }


def flush_collector_to_client(
    collector: RunCollector,
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
