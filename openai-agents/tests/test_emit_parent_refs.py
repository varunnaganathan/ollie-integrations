"""Orphan parent_span_ref is dropped before wire validate."""

from __future__ import annotations

from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.emit import collector_to_wire_payload
from ollie_integrations_openai_agents.hooks import _collector_session_id, _runner_kwargs


def test_emit_drops_orphan_parent_span_ref():
    c = RunCollector(workflow_name="weather_assistant", input_text="hi")
    c.add_span(
        {
            "type": "tool",
            "name": "get_weather",
            "status": "success",
            "span_ref": "sp_tool_1",
            "parent_span_ref": "span_not_in_this_interaction",
        }
    )
    c.close(output="72F", success=True)
    wire = collector_to_wire_payload(c, agent_id="agent_test")
    spans = wire["interactions"][0]["events"]["spans"]
    assert spans
    assert "parent_span_ref" not in spans[0]


def test_emit_keeps_resolvable_parent():
    c = RunCollector(workflow_name="weather_assistant", input_text="hi")
    c.add_span({"type": "llm", "name": "m", "status": "success", "span_ref": "sp_llm_1"})
    c.add_span(
        {
            "type": "tool",
            "name": "get_weather",
            "status": "success",
            "span_ref": "sp_tool_1",
            "parent_span_ref": "sp_llm_1",
        }
    )
    c.close(output="72F", success=True)
    wire = collector_to_wire_payload(c, agent_id="agent_test")
    spans = {s["span_ref"]: s for s in wire["interactions"][0]["events"]["spans"]}
    assert spans["sp_tool_1"]["parent_span_ref"] == "sp_llm_1"


def test_runner_kwargs_strips_session_id():
    assert _runner_kwargs({"session_id": "x", "max_turns": 3}) == {"max_turns": 3}


def test_collector_session_prefers_env(monkeypatch):
    monkeypatch.setenv("OLLIE_SESSION_ID", "test-offline-abcd1234")
    assert _collector_session_id({"session_id": "ignored"}) == "test-offline-abcd1234"
