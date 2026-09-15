from helpers import build_single_turn_voice_tree

from ollie_integrations_livekit.emit import collector_to_wire_payload
from ollie_integrations_livekit.inventory import inventory_from_wire_payload


def test_emit_matches_structure():
    wire = collector_to_wire_payload(
        build_single_turn_voice_tree(),
        agent_id="agent_test",
        session_id="sess-voice-001",
    )
    assert wire["schema_version"] == 2
    assert wire["sdk"]["name"] == "ollie-integrations-livekit"
    assert wire["sdk"]["version"] == "0.2.0"
    assert wire["workflow"]["name"] == "sample_livekit_agent"
    assert len(wire["interactions"]) == 1
    turn = wire["interactions"][0]
    assert turn["name"] == "turn_1"
    assert turn["interaction_type"] == "conversational"
    spans = turn["events"]["spans"]
    types = {s["type"] for s in spans}
    assert types >= {"stt", "turn_detection", "agent", "tool", "tts", "llm"}
    tool = next(s for s in spans if s["type"] == "tool")
    agent = next(s for s in spans if s["type"] == "agent")
    assert tool["parent_span_ref"] == agent["span_ref"]
    llm = next(s for s in spans if s["type"] == "llm")
    assert llm["parent_span_ref"] == agent["span_ref"]


def test_voice_stages_are_spans_not_interactions():
    wire = collector_to_wire_payload(build_single_turn_voice_tree(), agent_id="agent_test")
    names = {ix["name"] for ix in wire["interactions"]}
    assert names == {"turn_1"}
    spans = wire["interactions"][0]["events"]["spans"]
    by_type = {s["type"]: s for s in spans if s["type"] != "llm"}
    assert by_type["stt"]["name"] == "stt"
    assert by_type["turn_detection"]["name"] == "turn_detection"
    assert by_type["tts"]["name"] == "tts"
    assert by_type["tool"]["name"] == "lookup_weather"


def test_golden_fixture_inventory():
    wire = collector_to_wire_payload(build_single_turn_voice_tree(), agent_id="agent_test")
    inv = inventory_from_wire_payload(wire)
    assert inv["interaction_count"] == 1
    assert inv["span_count"] >= 5
    assert {a["name"] for a in inv["agents"]} == {"support_agent"}
    assert {t["name"] for t in inv["tools"]} == {"lookup_weather"}
    assert {v["name"] for v in inv["voice_components"]} >= {"stt", "turn_detection", "tts"}
