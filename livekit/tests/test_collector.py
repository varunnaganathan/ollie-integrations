from helpers import build_single_turn_voice_tree

from ollie_integrations_livekit.collector import ExecutionSpanCollector


def test_open_close_agent_session():
    c = ExecutionSpanCollector(app_name="test_app")
    sid = c.open_agent_session(input_text="session_start")
    c.close_agent_session(sid, output_text="session_ended")
    nodes = c.nodes_in_order()
    assert len(nodes) == 1
    assert nodes[0].execution_type.value == "agent_session"


def test_single_turn_voice_stack():
    c = build_single_turn_voice_tree()
    nodes = c.nodes_in_order()
    types = [n.execution_type.value for n in nodes]
    assert types == [
        "agent_session",
        "user_turn",
        "stt",
        "turn_detection",
        "agent",
        "tool",
        "tts",
    ]


def test_content_redaction():
    c = ExecutionSpanCollector(app_name="redact", capture_content=False)
    sid = c.open_stt()
    c.close_stt(sid, output_text="secret", success=True)
    node = c.nodes_in_order()[0]
    assert node.input_text == ""
    assert any(e.get("name") == "livekit.content_redacted" for e in node.events)
