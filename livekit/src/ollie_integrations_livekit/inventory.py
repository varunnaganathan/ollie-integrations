"""Discover agent/tool/voice names from emitted wire payloads."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _iter_spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        events = ix.get("events")
        if isinstance(events, dict):
            spans = events.get("spans")
            if isinstance(spans, list):
                out.extend(s for s in spans if isinstance(s, dict))
        elif isinstance(events, list):
            # Legacy tree shape (pre-0.2.0): one interaction per stage
            for ev in events:
                if isinstance(ev, dict) and ev.get("name") == "livekit.execution_started":
                    payload_et = (ev.get("payload") or {}).get("execution_type")
                    if payload_et:
                        out.append(
                            {
                                "type": str(payload_et),
                                "name": str(ix.get("name") or ""),
                            }
                        )
                    break
    return out


def inventory_from_wire_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Aggregate discovered names from a v2 LiveKit wire payload (turn + spans)."""
    agents: dict[str, int] = defaultdict(int)
    tools: dict[str, int] = defaultdict(int)
    sessions: dict[str, int] = defaultdict(int)
    turns: dict[str, int] = defaultdict(int)
    voice: dict[str, int] = defaultdict(int)

    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        wf_name = str(workflow.get("name") or "").strip()
        if wf_name:
            sessions[wf_name] += 1

    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        name = str(ix.get("name") or "").strip()
        if name.startswith("turn_") or str(ix.get("interaction_type") or "") == "conversational":
            if name:
                turns[name] += 1

    for span in _iter_spans(payload):
        name = str(span.get("name") or "").strip()
        st = str(span.get("type") or span.get("kind") or "").strip()
        if not name:
            continue
        if st == "agent":
            agents[name] += 1
        elif st == "tool":
            tools[name] += 1
        elif st in ("stt", "turn_detection", "tts"):
            voice[name] += 1

    return {
        "agents": [{"name": n, "count": c} for n, c in sorted(agents.items())],
        "tools": [{"name": n, "count": c} for n, c in sorted(tools.items())],
        "sessions": [{"name": n, "count": c} for n, c in sorted(sessions.items())],
        "turns": [{"name": n, "count": c} for n, c in sorted(turns.items())],
        "voice_components": [{"name": n, "count": c} for n, c in sorted(voice.items())],
        "interaction_count": len(payload.get("interactions") or []),
        "span_count": sum(
            len((ix.get("events") or {}).get("spans") or [])
            if isinstance(ix.get("events"), dict)
            else 0
            for ix in (payload.get("interactions") or [])
            if isinstance(ix, dict)
        ),
    }


def suggest_operational_types(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """Heuristic operational type suggestions (Phase 1b preview)."""
    suggestions: list[dict[str, str]] = []

    for entry in inventory.get("voice_components") or []:
        name = str(entry.get("name") or "").lower()
        if name == "stt" or "stt" in name:
            suggestions.append(
                {
                    "component_name": entry.get("name", ""),
                    "suggested_operational_type": "Acquire Information",
                    "confidence": "platform_default",
                }
            )
        elif "turn" in name:
            suggestions.append(
                {
                    "component_name": entry.get("name", ""),
                    "suggested_operational_type": "Evaluate Information",
                    "confidence": "platform_default",
                }
            )
        elif name == "tts" or "tts" in name:
            suggestions.append(
                {
                    "component_name": entry.get("name", ""),
                    "suggested_operational_type": "Produce Output",
                    "confidence": "platform_default",
                }
            )

    agent_rules = [
        (("research", "search", "retrieve", "fetch"), "Acquire Information"),
        (("critic", "review", "eval", "judge", "verify", "plan", "planner"), "Evaluate Information"),
        (("writer", "compose", "draft", "produce", "summar"), "Produce Output"),
    ]
    for entry in inventory.get("agents") or []:
        name = str(entry.get("name") or "").lower()
        for keywords, op_type in agent_rules:
            if any(k in name for k in keywords):
                suggestions.append(
                    {
                        "component_name": entry.get("name", ""),
                        "suggested_operational_type": op_type,
                        "confidence": "heuristic",
                    }
                )
                break

    tool_rules = [
        (("write", "update", "modify", "save", "delete"), "Modify State"),
        (("search", "fetch", "read", "get", "retrieve", "lookup", "weather"), "Acquire Information"),
    ]
    for entry in inventory.get("tools") or []:
        name = str(entry.get("name") or "").lower()
        for keywords, op_type in tool_rules:
            if any(k in name for k in keywords):
                suggestions.append(
                    {
                        "component_name": entry.get("name", ""),
                        "suggested_operational_type": op_type,
                        "confidence": "heuristic",
                    }
                )
                break

    return suggestions
