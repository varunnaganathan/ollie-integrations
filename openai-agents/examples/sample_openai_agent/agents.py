"""Build sample OpenAI Agents for Ollie demos."""

from __future__ import annotations


def build_single_tool_agent():
    from agents import Agent, function_tool

    @function_tool
    def get_weather(city: str) -> str:
        """Return mock weather for a city."""
        return f"It's 72°F and sunny in {city}."

    return Agent(
        name="weather_assistant",
        instructions="Use get_weather when the user asks about weather.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )


def build_handoff_agents():
    from agents import Agent, function_tool

    @function_tool
    def process_refund(order_id: str) -> str:
        """Process a refund for an order."""
        return f"Refund approved for order {order_id}."

    billing = Agent(
        name="Billing",
        instructions="Process refunds with process_refund.",
        tools=[process_refund],
        model="gpt-4o-mini",
    )

    triage = Agent(
        name="Triage",
        instructions="Route billing questions to Billing.",
        handoffs=[billing],
        model="gpt-4o-mini",
    )
    return triage, billing
