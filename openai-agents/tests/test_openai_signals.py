from __future__ import annotations

from ollie_integrations_openai_agents.signals import derived_signals, direct_signals, instrument_events


def test_no_delegation_from_handoff_span():
    _, ctx = direct_signals(spans=[{"type": "handoff", "name": "A → B", "status": "success"}])
    assert not any(s["name"] == "delegation" for s in ctx)


def test_guardrail_blocked_trigger():
    trig, _ = direct_signals(
        spans=[{"type": "guardrail", "name": "pii", "status": "failure", "triggered": True}]
    )
    assert any(s["name"] == "guardrail_blocked" for s in trig)


def test_repeated_tool_error_trigger():
    spans = [
        {"type": "tool", "name": "search", "status": "failure"},
        {"type": "tool", "name": "search", "status": "failure"},
    ]
    trig, _ = derived_signals(spans=spans, output="ok", success=True, latency_ms=100)
    assert any(s["name"] == "repeated_tool_error" for s in trig)


def test_p2_trio_on_bad_session():
    _, ctx = derived_signals(spans=[], output="", success=False, latency_ms=60_000)
    names = {s["name"] for s in ctx}
    assert "runtime_failure" in names
    assert "empty_final_response" in names
    assert "high_latency" in names


def test_instrument_events_no_used_tool_hit():
    events, hits = instrument_events(
        spans=[{"type": "tool", "name": "get_weather", "status": "success", "span_ref": "sp_1"}],
        output="72°F",
        success=True,
        latency_ms=500,
    )
    assert events["trigger"] == []
    assert events["context"] == []
    assert "spans" in events
    assert not any(h["signal"] == "used_tool" for h in hits)
    assert hits == []
