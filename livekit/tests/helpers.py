"""Build synthetic LiveKit collector trees for unit tests."""

from __future__ import annotations

from ollie_integrations_livekit.collector import ExecutionSpanCollector


def build_single_turn_voice_tree(*, app_name: str = "sample_livekit_agent") -> ExecutionSpanCollector:
    c = ExecutionSpanCollector(
        app_name=app_name,
        session_id="sess-voice-001",
        room="room-demo",
        participant="user-1",
    )
    sess = c.open_agent_session(input_text="session_start room=room-demo")
    turn = c.open_user_turn(input_text="[user_audio]")
    stt = c.open_stt(input_text="[audio_stream]")
    c.close_stt(stt, output_text="What's the weather in NYC?", success=True)
    td = c.open_turn_detection(input_text="What's the weather in NYC?")
    c.close_turn_detection(td, output_text="turn_complete", success=True)
    agent = c.open_agent("support_agent", input_text="What's the weather in NYC?")
    c.add_event(agent, "livekit.llm_start")
    tool = c.open_tool("lookup_weather", input_text='{"city": "NYC"}')
    c.close_tool(tool, output_text='{"temp_f": 72, "condition": "sunny"}', success=True)
    c.add_event(agent, "livekit.llm_end")
    c.close_agent(agent, output_text="It's 72°F and sunny in NYC.", success=True)
    tts = c.open_tts(input_text="It's 72°F and sunny in NYC.")
    c.close_tts(tts, output_text="[audio_stream]", success=True)
    c.close_user_turn(turn, output_text="[agent_audio]", success=True)
    c.close_agent_session(sess, output_text="session_ended", success=True)
    return c


def build_multi_turn_voice_tree(*, app_name: str = "sample_livekit_agent") -> ExecutionSpanCollector:
    c = build_single_turn_voice_tree(app_name=app_name)
    # Re-open session close was done — rebuild: use nodes before close
    # Simpler: build fresh two-turn tree
    c2 = ExecutionSpanCollector(
        app_name=app_name,
        session_id="sess-voice-002",
        room="room-demo",
        participant="user-1",
    )
    sess = c2.open_agent_session(input_text="session_start room=room-demo")
    for user_msg, agent_reply in (
        ("What's the weather in NYC?", "It's 72°F and sunny in NYC."),
        ("Thanks!", "You're welcome!"),
    ):
        turn = c2.open_user_turn(input_text="[user_audio]")
        stt = c2.open_stt(input_text="[audio_stream]")
        c2.close_stt(stt, output_text=user_msg, success=True)
        td = c2.open_turn_detection(input_text=user_msg)
        c2.close_turn_detection(td, output_text="turn_complete", success=True)
        ag = c2.open_agent("support_agent", input_text=user_msg)
        c2.close_agent(ag, output_text=agent_reply, success=True)
        tts = c2.open_tts(input_text=agent_reply)
        c2.close_tts(tts, output_text="[audio_stream]", success=True)
        c2.close_user_turn(turn, output_text="[agent_audio]", success=True)
    c2.close_agent_session(sess, output_text="session_ended", success=True)
    return c2
