from __future__ import annotations

from types import SimpleNamespace

from ollie_integrations_openai_agents.processor import _map_span


class _FakeSpan:
    def __init__(self, *, span_data, started_at=None, ended_at=None, error=None, span_id="sp1", parent_id=None):
        self.span_data = span_data
        self.started_at = started_at
        self.ended_at = ended_at
        self.error = error
        self.span_id = span_id
        self.parent_id = parent_id


def test_response_span_uses_sdk_timestamps_model_and_finish_reason():
    response = SimpleNamespace(
        model="gpt-4o-mini",
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    span = _FakeSpan(
        span_data=SimpleNamespace(
            type="response",
            response=response,
            usage={"input_tokens": 10, "output_tokens": 5},
        ),
        started_at="2026-06-30T12:00:00.000Z",
        ended_at="2026-06-30T12:00:01.500Z",
    )
    mapped = _map_span(span, {})
    assert mapped is not None
    assert mapped["name"] == "gpt-4o-mini"
    assert mapped["duration_ms"] == 1500
    assert mapped["token_count"] == 15
    assert mapped["finish_reason"] == "max_output_tokens"
    assert mapped["started_at"] == "2026-06-30T12:00:00.000Z"
    assert mapped["ended_at"] == "2026-06-30T12:00:01.500Z"
    assert mapped["span_ref"] == "sp1"


def test_response_span_carries_parent_span_ref():
    span = _FakeSpan(
        span_data=SimpleNamespace(type="response", response=None, usage=None),
        span_id="sp_child",
        parent_id="sp_parent",
    )
    mapped = _map_span(span, {})
    assert mapped is not None
    assert mapped["span_ref"] == "sp_child"
    assert mapped["parent_span_ref"] == "sp_parent"


def test_agent_handoff_guardrail_blank_io_and_names():
    agent = _map_span(
        _FakeSpan(
            span_data=SimpleNamespace(type="agent", name="Triage", input="should-ignore", output="nope"),
            span_id="a1",
        ),
        {},
    )
    assert agent is not None
    assert agent["type"] == "agent"
    assert agent["name"] == "Triage"
    assert agent["input"] == {}
    assert agent["output"] == {}

    handoff = _map_span(
        _FakeSpan(
            span_data=SimpleNamespace(
                type="handoff",
                from_agent="Triage",
                to_agent="Billing",
                input={"x": 1},
            ),
            span_id="h1",
        ),
        {},
    )
    assert handoff is not None
    assert handoff["type"] == "handoff"
    assert handoff["name"] == "Triage → Billing"
    assert handoff["from_agent"] == "Triage"
    assert handoff["to_agent"] == "Billing"
    assert handoff["input"] == {}
    assert handoff["output"] == {}

    guard = _map_span(
        _FakeSpan(
            span_data=SimpleNamespace(type="guardrail", name="pii_check", triggered=True, output="leak"),
            span_id="g1",
        ),
        {},
    )
    assert guard is not None
    assert guard["type"] == "guardrail"
    assert guard["name"] == "pii_check"
    assert guard["status"] == "failure"
    assert guard["triggered"] is True
    assert guard["input"] == {}
    assert guard["output"] == {}


def test_custom_span_mapped_with_optional_io():
    mapped = _map_span(
        _FakeSpan(
            span_data=SimpleNamespace(
                type="custom",
                name="save_to_db",
                data={"table": "orders"},
                output={"ok": True},
            ),
            span_id="c1",
        ),
        {},
    )
    assert mapped is not None
    assert mapped["type"] == "custom"
    assert mapped["name"] == "save_to_db"
    assert mapped["input"] == {"table": "orders"}
    assert mapped["output"] == {"ok": True}


def test_turn_and_task_still_dropped():
    assert _map_span(_FakeSpan(span_data=SimpleNamespace(type="turn")), {}) is None
    assert _map_span(_FakeSpan(span_data=SimpleNamespace(type="task")), {}) is None
