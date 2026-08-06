"""Emit and collector unit tests for OpenAI Agents integration."""

from __future__ import annotations

from openai_helpers import build_handoff_run, build_single_tool_run
from ollie_integrations_openai_agents.emit import collector_to_wire_payload


def test_single_run_wire_shape():
    wire = collector_to_wire_payload(build_single_tool_run(), agent_id="agent_test", session_id="sess-1")
    assert wire["schema_version"] == 2
    assert len(wire["interactions"]) == 1
    ix = wire["interactions"][0]
    assert ix["interaction_type"] == "run"
    assert ix["events"]["trigger"] == []
    assert ix["events"]["context"] == []
    assert any(h.get("signal") == "used_tool" for h in ix.get("_signal_hits") or [])


def test_handoff_delegation_signal():
    wire = collector_to_wire_payload(build_handoff_run(), agent_id="agent_test", session_id="sess-2")
    hits = {h["signal"] for h in wire["interactions"][0].get("_signal_hits") or []}
    assert "delegation" in hits
