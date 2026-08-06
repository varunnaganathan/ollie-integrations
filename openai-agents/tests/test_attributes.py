"""Tests for add_interaction_attributes / add_span_attributes (OpenAI Agents)."""

from __future__ import annotations

from ollie_integrations_openai_agents.attributes import (
    add_interaction_attributes,
    add_span_attributes,
)
from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.emit import collector_to_wire_payload
from ollie_integrations_openai_agents.warehouse_span import warehouse_shape_span


def test_add_interaction_attributes_on_run():
    c = RunCollector(workflow_name="bot", input_text="hi")
    RunCollector.set_current(c)
    add_interaction_attributes({"user_tier": "pro", "request_id": "req-1"})
    c.close(output="ok", success=True)
    RunCollector.set_current(None)

    wire = collector_to_wire_payload(c, agent_id="agent_test")
    names = {a["name"]: a["value"] for a in wire["interactions"][0]["attributes"]}
    assert names["user_tier"] == "pro"
    assert names["request_id"] == "req-1"
    assert names["success"] is True


def test_add_span_attributes_merged_on_close():
    c = RunCollector(workflow_name="bot", input_text="hi")
    RunCollector.set_current(c)
    c.push_open_span("sp_tool_1")
    add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
    c.add_span(
        warehouse_shape_span(
            {
                "type": "tool",
                "name": "get_balance",
                "status": "success",
                "span_ref": "sp_tool_1",
                "duration_ms": 10,
            }
        )
    )
    c.pop_open_span("sp_tool_1")
    c.close(output="ok", success=True)
    RunCollector.set_current(None)

    wire = collector_to_wire_payload(c, agent_id="agent_test")
    tool = wire["interactions"][0]["events"]["spans"][0]
    props = tool["properties"]
    assert props["vendor"] == "core_ledger"
    assert props["retry_count"] == 0
    assert props["kind"] == "tool"
    assert props["name"] == "get_balance"


def test_add_span_attributes_noop_without_open_span():
    c = RunCollector(workflow_name="bot", input_text="hi")
    RunCollector.set_current(c)
    add_span_attributes({"should_not": "land"})
    c.close(output="ok", success=True)
    RunCollector.set_current(None)

    wire = collector_to_wire_payload(c, agent_id="agent_test")
    names = {a["name"] for a in wire["interactions"][0]["attributes"]}
    assert "should_not" not in names
    assert wire["interactions"][0]["events"]["spans"] == []


def test_custom_attrs_do_not_overwrite_reserved():
    c = RunCollector(workflow_name="bot", input_text="hi")
    RunCollector.set_current(c)
    c.push_open_span("sp_1")
    add_span_attributes({"kind": "evil", "name": "hijack", "status": "failure"})
    c.add_span(
        warehouse_shape_span(
            {
                "type": "agent",
                "name": "Assistant",
                "status": "success",
                "span_ref": "sp_1",
                "duration_ms": 5,
            }
        )
    )
    c.pop_open_span("sp_1")
    c.close(output="ok", success=True)
    RunCollector.set_current(None)

    props = collector_to_wire_payload(c, agent_id="agent_test")["interactions"][0]["events"]["spans"][0][
        "properties"
    ]
    assert props["kind"] == "agent"
    assert props["name"] == "Assistant"
    assert props["status"] == "success"
