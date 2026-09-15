"""Minimal LiveKit voice agent example."""

from __future__ import annotations

APP_NAME = "sample_livekit_agent"
AGENT_NAME = "support_agent"
TOOL_NAME = "lookup_weather"
USER_MESSAGE = "What's the weather in NYC?"


def lookup_weather(city: str) -> dict:
    """Look up weather for a city."""
    return {"temp_f": 72, "condition": "sunny", "city": city}


def build_agent():
    from livekit.agents import Agent, function_tool

    return Agent(
        instructions=(
            "You are a helpful voice assistant named support_agent. "
            "When asked about weather in a city, call lookup_weather with the city name. "
            "Reply briefly with the temperature and condition."
        ),
        tools=[function_tool(lookup_weather)],
    )


def build_session():
    from livekit.agents import AgentSession
    from livekit.plugins import silero
    from livekit.plugins.turn_detector.multilingual import MultilingualModel

    return AgentSession(
        stt="deepgram/nova-3:multi",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )
