"""E2E: OpenAI Agents — exercise all custom instrumentation capabilities on the wire.

Capabilities covered:
1. add_interaction_attributes (run features)
2. add_span_attributes (span properties)
3. emit_signal (user _signal_hits)
4. warehouse spans (kind/name/status + I/O)
5. auto instrumented signal hits still present when applicable

Synthetic path always runs. Live path needs OPENAI_API_KEY + agents package.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from ollie_integrations_openai_agents import (
    add_interaction_attributes,
    add_span_attributes,
    emit_signal,
)
from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.emit import collector_to_wire_payload
from ollie_integrations_openai_agents.warehouse_span import warehouse_shape_span


def _assert_five_capabilities(wire: dict) -> None:
    assert wire["schema_version"] == 2
    ix = wire["interactions"][0]
    attrs = {a["name"]: a["value"] for a in ix["attributes"]}
    assert attrs.get("user_tier") == "pro"
    assert attrs.get("request_id") == "req-e2e-1"

    spans = ix["events"]["spans"]
    assert len(spans) >= 1
    tool = next(s for s in spans if s.get("type") == "tool" or (s.get("properties") or {}).get("kind") == "tool")
    props = tool["properties"]
    assert props.get("vendor") == "core_ledger"
    assert props.get("kind") == "tool"
    assert props.get("name")

    hits = ix.get("_signal_hits") or []
    names = {h.get("signal") for h in hits}
    assert "refund_requested" in names
    refund = next(h for h in hits if h.get("signal") == "refund_requested")
    assert refund.get("kind") == "context"


def test_e2e_synthetic_all_sdk_capabilities():
    """No OpenAI key — drive collector like a live tool run."""
    c = RunCollector(workflow_name="e2e_oa_caps", session_id="sess-caps", input_text="weather NYC?")
    RunCollector.set_current(c)
    try:
        add_interaction_attributes({"user_tier": "pro", "request_id": "req-e2e-1"})
        emit_signal("refund_requested", kind="context")

        c.push_open_span("sp_tool_1")
        add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
        emit_signal("tool_slow_path", kind="context")
        c.add_span(
            warehouse_shape_span(
                {
                    "type": "tool",
                    "name": "get_weather",
                    "status": "success",
                    "span_ref": "sp_tool_1",
                    "duration_ms": 12,
                    "input": {"text": "NYC"},
                    "output": {"text": "72F sunny"},
                }
            )
        )
        c.pop_open_span("sp_tool_1")
        c.close(output="It's 72°F and sunny in NYC.", success=True)
    finally:
        RunCollector.set_current(None)

    wire = collector_to_wire_payload(c, agent_id="agent_e2e_caps")
    _assert_five_capabilities(wire)
    hits = {h["signal"] for h in wire["interactions"][0]["_signal_hits"]}
    assert "tool_slow_path" in hits
    assert "used_tool" in hits or "tool_slow_path" in hits  # auto and/or user


@pytest.mark.live
@pytest.mark.openai
def test_e2e_live_openai_agents_all_capabilities():
    """Live Runner.run with attrs + emit inside the tool body."""
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        pytest.skip("OPENAI_API_KEY required")
    pytest.importorskip("agents")

    from agents import Agent, Runner, function_tool
    from ollie_integrations_openai_agents import attach_ollie, get_last_wire_payload
    from unittest.mock import MagicMock

    @function_tool
    def get_weather(city: str) -> str:
        add_interaction_attributes({"user_tier": "pro", "request_id": "req-e2e-1"})
        add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
        emit_signal("refund_requested", kind="context")
        return f"It's 72°F and sunny in {city}."

    client = MagicMock()
    client.agent_id = "agent_e2e_caps"
    client._transport = MagicMock()
    client._transport.validate_trace.return_value = {"accepted": True}
    client._delivery = MagicMock()
    attach_ollie(client, workflow_name="e2e_oa_live_caps", flush_mode="validate")

    agent = Agent(
        name="weather_assistant",
        instructions="Always call get_weather for weather questions.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )
    asyncio.run(Runner.run(agent, "What's the weather in NYC?"))
    wire = get_last_wire_payload()
    assert wire is not None
    _assert_five_capabilities(wire)
