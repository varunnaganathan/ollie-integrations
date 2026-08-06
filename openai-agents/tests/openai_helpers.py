"""Build synthetic RunCollector for unit tests."""

from __future__ import annotations

from ollie_integrations_openai_agents.collector import RunCollector


def build_single_tool_run() -> RunCollector:
    c = RunCollector(
        workflow_name="weather_assistant",
        session_id="sess-001",
        input_text="What's the weather in NYC?",
    )
    c.add_span(
        {
            "type": "llm",
            "name": "gpt-4o-mini",
            "status": "success",
            "span_ref": "sp_llm_1",
            "duration_ms": 400,
            "token_count": 50,
        }
    )
    c.add_span(
        {
            "type": "tool",
            "name": "get_weather",
            "status": "success",
            "span_ref": "sp_tool_1",
            "parent_span_ref": "sp_llm_1",
            "duration_ms": 120,
        }
    )
    c.add_span(
        {
            "type": "llm",
            "name": "gpt-4o-mini",
            "status": "success",
            "span_ref": "sp_llm_2",
            "duration_ms": 300,
            "token_count": 40,
        }
    )
    c.close(output="It's 72°F and sunny in New York.", success=True)
    return c


def build_handoff_run() -> RunCollector:
    c = RunCollector(
        workflow_name="support_pipeline",
        input_text="I need a refund for order 4821",
    )
    c.add_span(
        {
            "type": "llm",
            "name": "gpt-4o-mini",
            "status": "success",
            "span_ref": "sp_llm_1",
            "duration_ms": 200,
        }
    )
    c.add_span(
        {
            "type": "handoff",
            "name": "Triage → Billing",
            "status": "success",
            "span_ref": "sp_handoff_1",
            "from_agent": "Triage",
            "to_agent": "Billing",
        }
    )
    c.add_span(
        {
            "type": "tool",
            "name": "process_refund",
            "status": "success",
            "span_ref": "sp_tool_1",
            "duration_ms": 90,
        }
    )
    c.add_span(
        {
            "type": "llm",
            "name": "gpt-4o-mini",
            "status": "success",
            "span_ref": "sp_llm_2",
            "duration_ms": 180,
        }
    )
    c.close(output="Refund approved.", success=True)
    return c
