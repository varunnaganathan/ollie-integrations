"""Google ADK sample agents covering common Runner topologies."""

from __future__ import annotations

import os

APP_NAME = "sample_adk_agent"
DEFAULT_MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

# Single-agent
SINGLE_AGENT_NAME = "calculator_agent"
SINGLE_TOOL_NAME = "add_numbers"
SINGLE_USER_MESSAGE = "What is 12 + 7?"

# Shared multi-agent names
ORCHESTRATOR_NAME = "orchestrator"
RESEARCHER_NAME = "researcher"
MULTI_TOOL_NAME = "search_filings"
MULTI_USER_MESSAGE = "Summarize ACME 10-K risk factors"

# Parallel topology
PARALLEL_AGENT_A = "risk_analyst"
PARALLEL_AGENT_B = "market_analyst"
PARALLEL_USER_MESSAGE = "What are ACME's main business risks?"

# Loop topology
LOOP_CRITIC_NAME = "critic"
LOOP_USER_MESSAGE = "Draft one sentence on ACME regulatory risk."

# Delegation topology (LlmAgent sub_agents / branch transfer)
DELEGATION_USER_MESSAGE = MULTI_USER_MESSAGE


def add_numbers(a: int, b: int) -> dict:
    """Add two integers and return the sum."""
    return {"result": a + b}


def search_filings(query: str) -> dict:
    """Search SEC filings and return relevant snippets."""
    return {
        "query": query,
        "snippets": [
            "Competition risk: ACME faces intense competition in core markets.",
            "Regulatory risk: evolving compliance requirements may increase costs.",
        ],
    }


def _researcher_agent():
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool

    return LlmAgent(
        name=RESEARCHER_NAME,
        model=DEFAULT_MODEL,
        instruction=(
            "You are a research assistant. "
            "When asked about company filings, call search_filings with the user's query. "
            "Summarize the returned snippets in 1-2 sentences."
        ),
        tools=[FunctionTool(search_filings)],
    )


def build_single_agent():
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool

    return LlmAgent(
        name=SINGLE_AGENT_NAME,
        model=DEFAULT_MODEL,
        instruction=(
            "You are a calculator assistant. "
            "When the user asks for arithmetic, call add_numbers with integer arguments. "
            "Reply with the numeric result only."
        ),
        tools=[FunctionTool(add_numbers)],
    )


def build_sequential_agent():
    from google.adk.agents import LlmAgent, SequentialAgent

    researcher = _researcher_agent()
    orchestrator = LlmAgent(
        name=ORCHESTRATOR_NAME,
        model=DEFAULT_MODEL,
        instruction=(
            "You are an orchestrator. "
            "Rephrase the user's filing question clearly for the researcher. "
            "Do not call tools yourself."
        ),
    )
    return SequentialAgent(
        name=f"{ORCHESTRATOR_NAME}_pipeline",
        sub_agents=[orchestrator, researcher],
    )


def build_parallel_agent():
    from google.adk.agents import LlmAgent, ParallelAgent

    risk_analyst = LlmAgent(
        name=PARALLEL_AGENT_A,
        model=DEFAULT_MODEL,
        instruction="In one sentence, describe competition risk for the company in the user question.",
    )
    market_analyst = LlmAgent(
        name=PARALLEL_AGENT_B,
        model=DEFAULT_MODEL,
        instruction="In one sentence, describe market risk for the company in the user question.",
    )
    return ParallelAgent(
        name="parallel_research",
        sub_agents=[risk_analyst, market_analyst],
    )


def build_loop_agent():
    from google.adk.agents import LlmAgent, LoopAgent

    critic = LlmAgent(
        name=LOOP_CRITIC_NAME,
        model=DEFAULT_MODEL,
        instruction=(
            "You are a critic. Improve the user's draft sentence on regulatory risk. "
            "Reply with a single improved sentence."
        ),
    )
    return LoopAgent(
        name="review_loop",
        sub_agents=[critic],
        max_iterations=2,
    )


def build_delegation_agent():
    from google.adk.agents import LlmAgent

    researcher = _researcher_agent()
    return LlmAgent(
        name=ORCHESTRATOR_NAME,
        model=DEFAULT_MODEL,
        instruction=(
            "You are an orchestrator. "
            "For SEC filing or 10-K questions, always transfer to the researcher sub-agent. "
            "Return the researcher's answer verbatim."
        ),
        sub_agents=[researcher],
    )


_TOPOLOGY_BUILDERS = {
    "single": build_single_agent,
    "sequential": build_sequential_agent,
    "multi": build_sequential_agent,  # alias
    "parallel": build_parallel_agent,
    "loop": build_loop_agent,
    "delegation": build_delegation_agent,
}

_TOPOLOGY_MESSAGES = {
    "single": SINGLE_USER_MESSAGE,
    "sequential": MULTI_USER_MESSAGE,
    "multi": MULTI_USER_MESSAGE,
    "parallel": PARALLEL_USER_MESSAGE,
    "loop": LOOP_USER_MESSAGE,
    "delegation": DELEGATION_USER_MESSAGE,
}


def build_root_agent(*, mode: str = "sequential"):
    builder = _TOPOLOGY_BUILDERS.get(mode)
    if builder is None:
        raise ValueError(f"unknown mode: {mode!r}; expected one of {sorted(_TOPOLOGY_BUILDERS)}")
    return builder()


def default_message_for_mode(mode: str) -> str:
    if mode not in _TOPOLOGY_MESSAGES:
        raise ValueError(f"unknown mode: {mode!r}")
    return _TOPOLOGY_MESSAGES[mode]


def build_runner(*, mode: str = "sequential"):
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    session_service = InMemorySessionService()
    return Runner(
        app_name=APP_NAME,
        agent=build_root_agent(mode=mode),
        session_service=session_service,
    )


def user_content(text: str):
    from google.genai import types

    return types.Content(role="user", parts=[types.Part(text=text)])
