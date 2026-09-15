"""Normalize LiveKit collector tree to turn interactions + events.spans."""

from __future__ import annotations

from typing import Any

from ollie_integrations_livekit.collector import ExecutionSpanCollector, utc_now_iso
from ollie_integrations_livekit.models import ExecutionType, LiveKitExecutionNode
from ollie_integrations_livekit.serialize import truncate

_SPAN_EXEC_TYPES = frozenset(
    {
        ExecutionType.STT,
        ExecutionType.TURN_DETECTION,
        ExecutionType.AGENT,
        ExecutionType.TOOL,
        ExecutionType.TTS,
    }
)

_EXEC_TO_SPAN_TYPE = {
    ExecutionType.STT: "stt",
    ExecutionType.TURN_DETECTION: "turn_detection",
    ExecutionType.AGENT: "agent",
    ExecutionType.TOOL: "tool",
    ExecutionType.TTS: "tts",
}

_RESERVED_PROP_KEYS = frozenset(
    {
        "kind",
        "name",
        "status",
        "duration_ms",
        "latency_ms",
        "success",
        "error_type",
    }
)


def _text_io_dict(text: str | None) -> dict[str, Any]:
    s = str(text or "").strip()
    if not s:
        return {}
    return {"text": s}


def _attr_value(node: LiveKitExecutionNode, name: str) -> Any:
    for a in node.attributes:
        if a.get("name") == name:
            return a.get("value")
    return None


def _merge_custom_span_properties(node: LiveKitExecutionNode, props: dict[str, Any]) -> None:
    for a in node.attributes:
        key = str(a.get("name") or "").strip()
        if not key or key in _RESERVED_PROP_KEYS or key in props:
            continue
        props[key] = a.get("value")


def _event_names(node: LiveKitExecutionNode) -> set[str]:
    out: set[str] = set()
    for ev in node.events:
        if isinstance(ev, dict):
            n = str(ev.get("name") or "").strip()
            if n:
                out.add(n)
    return out


def _event_at(node: LiveKitExecutionNode, name: str) -> str | None:
    for ev in node.events:
        if isinstance(ev, dict) and str(ev.get("name") or "") == name:
            at = ev.get("at")
            return str(at) if at else None
    return None


def _node_to_span(
    node: LiveKitExecutionNode,
    *,
    capture_content: bool,
    nodes_by_id: dict[str, LiveKitExecutionNode],
) -> dict[str, Any]:
    span_type = _EXEC_TO_SPAN_TYPE[node.execution_type]
    status = "success" if node.success else "failure"
    props: dict[str, Any] = {
        "kind": span_type,
        "name": node.name,
        "status": status,
    }
    latency = _attr_value(node, "latency_ms")
    if latency is not None:
        props["duration_ms"] = int(latency)
    err_type = _attr_value(node, "error_type")
    if err_type is not None:
        props["error_type"] = str(err_type)
    _merge_custom_span_properties(node, props)

    inp = node.input_text if capture_content else ""
    out = node.output_text if capture_content else ""
    span: dict[str, Any] = {
        "type": span_type,
        "name": node.name,
        "status": status,
        "span_ref": node.node_id,
        "started_at": node.started_at,
        "ended_at": node.ended_at or node.started_at,
        "input": _text_io_dict(inp),
        "output": _text_io_dict(out if out is not None else ""),
        "properties": props,
    }
    if latency is not None:
        span["duration_ms"] = int(latency)

    parent_id = node.parent_id
    if parent_id:
        parent = nodes_by_id.get(parent_id)
        if parent is not None and parent.execution_type in _SPAN_EXEC_TYPES:
            span["parent_span_ref"] = parent_id
    return span


def _llm_span_from_agent(agent: LiveKitExecutionNode) -> dict[str, Any] | None:
    names = _event_names(agent)
    if "livekit.llm_start" not in names and "livekit.llm_end" not in names:
        return None
    started = _event_at(agent, "livekit.llm_start") or agent.started_at
    ended = _event_at(agent, "livekit.llm_end") or agent.ended_at or agent.started_at
    status = "success" if agent.success else "failure"
    return {
        "type": "llm",
        "name": "llm",
        "status": status,
        "span_ref": f"{agent.node_id}_llm",
        "parent_span_ref": agent.node_id,
        "started_at": started,
        "ended_at": ended,
        "input": {},
        "output": {},
        "properties": {
            "kind": "llm",
            "name": "llm",
            "status": status,
        },
    }


def _descendants_of(turn_id: str, nodes: list[LiveKitExecutionNode]) -> list[LiveKitExecutionNode]:
    by_id = {n.node_id: n for n in nodes}
    children: dict[str, list[str]] = {}
    for n in nodes:
        if n.parent_id:
            children.setdefault(n.parent_id, []).append(n.node_id)

    out: list[LiveKitExecutionNode] = []
    stack = list(children.get(turn_id, []))
    while stack:
        nid = stack.pop()
        node = by_id.get(nid)
        if node is None:
            continue
        out.append(node)
        stack.extend(children.get(nid, []))
    # Preserve collector order
    order = {n.node_id: i for i, n in enumerate(nodes)}
    out.sort(key=lambda n: order.get(n.node_id, 0))
    return out


def _turn_io(turn: LiveKitExecutionNode, kids: list[LiveKitExecutionNode]) -> tuple[str, str | None]:
    """Prefer STT transcript as input and agent reply as output."""
    stt_out = next(
        (k.output_text for k in kids if k.execution_type == ExecutionType.STT and k.output_text),
        None,
    )
    agent_out = next(
        (k.output_text for k in kids if k.execution_type == ExecutionType.AGENT and k.output_text is not None),
        None,
    )
    inp_raw = stt_out if stt_out else turn.input_text
    out_raw = agent_out if agent_out is not None else turn.output_text
    inp, _ = truncate(inp_raw)
    out, _ = truncate(out_raw)
    return inp, out if out_raw is not None else None


def normalize_collector(collector: ExecutionSpanCollector) -> list[dict[str, Any]]:
    """Map collector tree → one conversational interaction per user_turn with spans."""
    nodes = collector.nodes_in_order()
    if not nodes:
        raise ValueError("collector has no nodes")

    session = next((n for n in nodes if n.execution_type == ExecutionType.AGENT_SESSION), None)
    if session is None:
        raise ValueError("collector missing agent_session node")

    turns = [n for n in nodes if n.execution_type == ExecutionType.USER_TURN]
    if not turns:
        raise ValueError("collector missing user_turn nodes")

    nodes_by_id = {n.node_id: n for n in nodes}
    interactions: list[dict[str, Any]] = []

    for i, turn in enumerate(turns):
        kids = _descendants_of(turn.node_id, nodes)
        spans: list[dict[str, Any]] = []
        for kid in kids:
            if kid.execution_type not in _SPAN_EXEC_TYPES:
                continue
            spans.append(
                _node_to_span(
                    kid,
                    capture_content=collector.capture_content,
                    nodes_by_id=nodes_by_id,
                )
            )
            if kid.execution_type == ExecutionType.AGENT:
                llm = _llm_span_from_agent(kid)
                if llm is not None:
                    spans.append(llm)

        inp, out = _turn_io(turn, kids)
        turn_ok = turn.success and all(s.get("status") != "failure" for s in spans)
        attrs = [a for a in turn.attributes if isinstance(a, dict)]
        attrs = [a for a in attrs if a.get("name") not in ("success", "latency_ms")]
        attrs.append({"name": "success", "value": turn_ok})
        latency = _attr_value(turn, "latency_ms")
        if latency is not None:
            attrs.append({"name": "latency_ms", "value": int(latency)})

        interactions.append(
            {
                "interaction_ref": f"ix_{i}",
                "parent_interaction_ref": None,
                "interaction_type": "conversational",
                "name": turn.name,
                "input": inp,
                "output": out,
                "events": {"trigger": [], "context": [], "spans": spans},
                "attributes": attrs,
                "started_at": turn.started_at,
                "ended_at": turn.ended_at or utc_now_iso(),
            }
        )

    return interactions


def session_workflow_fields(collector: ExecutionSpanCollector) -> dict[str, Any]:
    """Workflow object + session attributes derived from agent_session node."""
    nodes = collector.nodes_in_order()
    session = next((n for n in nodes if n.execution_type == ExecutionType.AGENT_SESSION), None)
    if session is None:
        raise ValueError("collector missing agent_session node")
    return {
        "name": collector.app_name or session.name,
        "status": collector.status,
        "started_at": session.started_at,
        "ended_at": session.ended_at or utc_now_iso(),
        "attributes": list(session.attributes),
        "session_events": list(session.events),
    }
