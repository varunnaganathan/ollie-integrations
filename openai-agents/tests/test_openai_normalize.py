from __future__ import annotations

from openai_helpers import build_handoff_run, build_single_tool_run
from ollie_integrations_openai_agents.emit import collector_to_wire_payload
from ollie_integrations_openai_agents.normalize import normalize_collector


def test_single_run_one_interaction():
    raw = normalize_collector(build_single_tool_run())
    assert raw["interaction_type"] == "run"
    wire = collector_to_wire_payload(build_single_tool_run(), agent_id="agent_test")
    assert len(wire["interactions"]) == 1
    ix = wire["interactions"][0]
    assert ix["interaction_type"] == "run"
    assert "run" not in [s.get("type") for s in ix["events"]["spans"]]
    assert any(s["type"] == "tool" for s in ix["events"]["spans"])
    assert all(isinstance(s.get("properties"), dict) for s in ix["events"]["spans"])
    assert all(isinstance(s.get("input"), dict) for s in ix["events"]["spans"])
    assert all(isinstance(s.get("output"), dict) for s in ix["events"]["spans"])


def test_handoff_delegation_signal():
    wire = collector_to_wire_payload(build_handoff_run(), agent_id="agent_test")
    ix = wire["interactions"][0]
    assert ix["events"]["trigger"] == []
    assert ix["events"]["context"] == []
    hits = {h["signal"] for h in ix.get("_signal_hits") or []}
    assert "delegation" in hits
    assert "used_tool" in hits


def test_io_are_strings():
    wire = collector_to_wire_payload(build_single_tool_run(), agent_id="agent_test")
    ix = wire["interactions"][0]
    assert isinstance(ix["input"], str)
    assert isinstance(ix["output"], str)
    assert ix["input"].strip() or ix["output"].strip()
