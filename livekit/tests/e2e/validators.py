from __future__ import annotations

from typing import Any


def _span_types(payload: dict[str, Any]) -> set[str]:
    types: set[str] = set()
    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        events = ix.get("events")
        if not isinstance(events, dict):
            continue
        for sp in events.get("spans") or []:
            if isinstance(sp, dict) and sp.get("type"):
                types.add(str(sp["type"]))
    return types


def assert_turn_span_shape(payload: dict[str, Any]) -> None:
    """Assert AgentSession→workflow + turn interactions with stage spans."""
    interactions = payload.get("interactions") or []
    if not interactions:
        raise AssertionError("empty interactions")

    workflow = payload.get("workflow")
    if not isinstance(workflow, dict) or not str(workflow.get("name") or "").strip():
        raise AssertionError("workflow.name required")

    for ix in interactions:
        if not isinstance(ix, dict):
            raise AssertionError("interaction must be object")
        events = ix.get("events")
        if not isinstance(events, dict):
            raise AssertionError(f"{ix.get('name')}: events must be {{trigger,context,spans}} dict")
        spans = events.get("spans")
        if not isinstance(spans, list) or not spans:
            raise AssertionError(f"{ix.get('name')}: expected non-empty events.spans")
        for sp in spans:
            if not isinstance(sp, dict):
                raise AssertionError("span must be object")
            for req in ("type", "name", "status", "span_ref"):
                if not str(sp.get(req) or "").strip():
                    raise AssertionError(f"span missing {req}")
            if sp.get("status") not in ("success", "failure"):
                raise AssertionError(f"bad span status {sp.get('status')!r}")

        it = ix.get("interaction_type")
        if it is not None and str(it).strip() and str(it).strip() not in (
            "conversational",
            "unknown",
        ):
            # Prefer conversational; allow empty/null
            if str(it) in ("speech_recognition", "speech_synthesis", "turn_management", "external_tool_call"):
                raise AssertionError(
                    f"{ix.get('name')}: stage interaction_type {it!r} belongs on spans, not the turn"
                )


def assert_interaction_tree(payload: dict[str, Any]) -> None:
    """Backward-compatible name used by package tests — now turn+span shape."""
    assert_turn_span_shape(payload)


def assert_live_hook_tree(payload: dict[str, Any], *, text_mode: bool = False) -> None:
    """Assert wire payload came from attach_ollie hooks on a real session run."""
    assert payload.get("sdk", {}).get("name") == "ollie-integrations-livekit"
    assert_turn_span_shape(payload)

    types = _span_types(payload)
    if "agent" not in types and "llm" not in types:
        raise AssertionError("live e2e must include agent or llm span from hooks")

    if text_mode:
        if "agent" not in types:
            raise AssertionError("text-mode live e2e expected at least one agent span from hooks")
    else:
        for required in ("stt", "turn_detection", "tts"):
            if required not in types:
                raise AssertionError(f"voice live e2e missing span type {required!r}")
