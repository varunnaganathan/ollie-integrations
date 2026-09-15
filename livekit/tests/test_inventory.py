from helpers import build_single_turn_voice_tree

from ollie_integrations_livekit.emit import collector_to_wire_payload
from ollie_integrations_livekit.inventory import inventory_from_wire_payload, suggest_operational_types


def test_inventory_voice_components():
    wire = collector_to_wire_payload(build_single_turn_voice_tree(), agent_id="agent_test")
    inv = inventory_from_wire_payload(wire)
    voice_names = {v["name"] for v in inv["voice_components"]}
    assert "stt" in voice_names
    assert "turn_detection" in voice_names
    assert "tts" in voice_names


def test_suggest_operational_types():
    wire = collector_to_wire_payload(build_single_turn_voice_tree(), agent_id="agent_test")
    inv = inventory_from_wire_payload(wire)
    suggestions = suggest_operational_types(inv)
    ops = {s["suggested_operational_type"] for s in suggestions}
    assert "Acquire Information" in ops
    assert "Evaluate Information" in ops
    assert "Produce Output" in ops
