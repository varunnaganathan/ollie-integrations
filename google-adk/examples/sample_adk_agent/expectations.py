"""Expected normalized wire shape for sample_adk_agent (topology-aware)."""

from __future__ import annotations

from typing import Any

from sample_adk_agent.agent import (
    LOOP_CRITIC_NAME,
    ORCHESTRATOR_NAME,
    PARALLEL_AGENT_A,
    PARALLEL_AGENT_B,
    RESEARCHER_NAME,
    SINGLE_AGENT_NAME,
)


def _events(ix: dict[str, Any]) -> dict[str, Any]:
    events = ix.get("events")
    if not isinstance(events, dict):
        raise AssertionError(f"{ix.get('name')}: events must be a dict")
    return events


def _run_interaction(payload: dict[str, Any]) -> dict[str, Any]:
    interactions = payload.get("interactions") or []
    if len(interactions) != 1:
        raise AssertionError(f"expected one run interaction, got {len(interactions)}")
    run = interactions[0]
    if run.get("interaction_type") != "run":
        raise AssertionError(f"expected run interaction, got {run.get('interaction_type')!r}")
    return run


def _spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_events(_run_interaction(payload)).get("spans") or [])


def _agent_span_names(payload: dict[str, Any]) -> set[str]:
    return {str(s.get("name") or "") for s in _spans(payload) if s.get("type") == "agent"}


def assert_normalized_shape(payload: dict[str, Any]) -> None:
    interactions = payload.get("interactions") or []
    if not interactions:
        raise AssertionError("empty interactions")

    roots = [ix for ix in interactions if not ix.get("parent_interaction_ref")]
    if len(roots) != 1:
        raise AssertionError(f"expected one root run, got {len(roots)}")
    root = roots[0]
    if root.get("interaction_type") != "run":
        raise AssertionError(f"root must be run, got {root.get('interaction_type')!r}")

    for ix in interactions:
        itype = ix.get("interaction_type")
        if itype != "run":
            raise AssertionError(f"{ix.get('name')}: unexpected interaction_type {itype!r}")
        events = _events(ix)
        for key in ("trigger", "context", "spans"):
            if key not in events or not isinstance(events[key], list):
                raise AssertionError(f"{ix.get('name')}: events.{key} must be a list")
        for span in events["spans"]:
            if not span.get("type"):
                raise AssertionError(f"{ix.get('name')}: span missing type")
            if not span.get("span_ref"):
                raise AssertionError(f"{ix.get('name')}: span missing span_ref")


def assert_single_agent_wire(payload: dict[str, Any]) -> None:
    assert_normalized_shape(payload)
    agent_names = _agent_span_names(payload)
    if SINGLE_AGENT_NAME not in agent_names:
        raise AssertionError(f"expected {SINGLE_AGENT_NAME!r} agent span, got {sorted(agent_names)}")
    span_types = {s.get("type") for s in _spans(payload)}
    if "tool" not in span_types:
        raise AssertionError(f"expected tool span, got {span_types}")


def assert_sequential_wire(payload: dict[str, Any]) -> None:
    assert_normalized_shape(payload)
    agent_names = _agent_span_names(payload)
    if RESEARCHER_NAME not in agent_names:
        raise AssertionError(f"expected researcher agent span, got {sorted(agent_names)}")
    researcher_tools = [
        s for s in _spans(payload) if s.get("type") == "tool" and s.get("name")
    ]
    if not researcher_tools:
        raise AssertionError("expected at least one tool span")
    if len(agent_names) < 2:
        raise AssertionError(f"expected at least 2 agent spans, got {sorted(agent_names)}")


def assert_parallel_wire(payload: dict[str, Any]) -> None:
    assert_normalized_shape(payload)
    agent_names = _agent_span_names(payload)
    missing = {PARALLEL_AGENT_A, PARALLEL_AGENT_B} - agent_names
    if missing:
        raise AssertionError(f"parallel run missing agent spans for {sorted(missing)}; got {sorted(agent_names)}")


def assert_loop_wire(payload: dict[str, Any]) -> None:
    assert_normalized_shape(payload)
    critic_spans = [s for s in _spans(payload) if s.get("type") == "agent" and s.get("name") == LOOP_CRITIC_NAME]
    if len(critic_spans) < 2:
        raise AssertionError(
            f"loop max_iterations=2 expected >=2 {LOOP_CRITIC_NAME!r} agent spans, got {len(critic_spans)}"
        )


def assert_delegation_wire(payload: dict[str, Any]) -> None:
    assert_normalized_shape(payload)
    agent_names = _agent_span_names(payload)
    if RESEARCHER_NAME not in agent_names:
        raise AssertionError(f"delegation run missing researcher agent span; got {sorted(agent_names)}")
    if ORCHESTRATOR_NAME not in agent_names:
        raise AssertionError(f"delegation run missing orchestrator agent span; got {sorted(agent_names)}")
    if "tool" not in {s.get("type") for s in _spans(payload)}:
        raise AssertionError("delegation run missing tool span")


# Back-compat alias
assert_multi_agent_wire = assert_sequential_wire
