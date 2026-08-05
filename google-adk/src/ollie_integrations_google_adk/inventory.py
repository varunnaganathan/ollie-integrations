"""Discover agent/tool names from emitted wire payloads."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def inventory_from_wire_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Aggregate discovered agent and tool names from a normalized v2 wire payload."""
    agents: dict[str, int] = defaultdict(int)
    tools: dict[str, int] = defaultdict(int)
    llms: dict[str, int] = defaultdict(int)
    runs: dict[str, int] = defaultdict(int)

    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        itype = str(ix.get("interaction_type") or "").strip()
        name = str(ix.get("name") or "").strip()
        events = ix.get("events") if isinstance(ix.get("events"), dict) else {}
        spans = events.get("spans") if isinstance(events, dict) else []

        if itype == "run" and name:
            runs[name] += 1

        if isinstance(spans, list):
            for span in spans:
                if not isinstance(span, dict):
                    continue
                span_name = str(span.get("name") or "").strip()
                span_type = str(span.get("type") or "").strip()
                if not span_name:
                    continue
                if span_type == "tool":
                    tools[span_name] += 1
                elif span_type == "llm":
                    llms[span_name] += 1
                elif span_type == "agent":
                    agents[span_name] += 1

    return {
        "agents": [{"name": n, "count": c} for n, c in sorted(agents.items())],
        "tools": [{"name": n, "count": c} for n, c in sorted(tools.items())],
        "llms": [{"name": n, "count": c} for n, c in sorted(llms.items())],
        "workflows": [{"name": n, "count": c} for n, c in sorted(runs.items())],
        "interaction_count": len(payload.get("interactions") or []),
    }


def suggest_operational_types(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """Heuristic span-type suggestions from discovered agent names (Phase 1b preview)."""
    rules = [
        (("research", "search", "retrieve", "fetch"), "Acquire Information"),
        (("critic", "review", "eval", "judge", "verify"), "Evaluate Information"),
        (("writer", "compose", "draft", "produce", "summar"), "Produce Output"),
        (("plan", "planner", "orchestr"), "Evaluate Information"),
    ]
    suggestions: list[dict[str, str]] = []
    for entry in inventory.get("agents") or []:
        name = str(entry.get("name") or "").lower()
        for keywords, op_type in rules:
            if any(k in name for k in keywords):
                suggestions.append(
                    {
                        "agent_name": entry.get("name", ""),
                        "suggested_operational_type": op_type,
                        "confidence": "heuristic",
                    }
                )
                break
    return suggestions
