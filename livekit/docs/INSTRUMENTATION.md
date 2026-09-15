# LiveKit Agents

Automatic execution tracing for LiveKit voice agents — speech recognition, turn detection, reasoning, tools, and speech synthesis — with Ollie.

Ollie hooks `AgentSession` lifecycle and voice events. You add two lines at worker startup; your agent, plugins, and room wiring stay unchanged. No mapping profiles or OpenTelemetry configuration.

---

## Installation

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.4"
pip install "ollie-integrations-livekit[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@livekit-v0.2.0#subdirectory=livekit"
```

This installs `ollie-sdk`, `livekit-agents`, and common plugins. Add any additional LiveKit plugins your agent already uses (Deepgram, Cartesia, etc.).

---

## Quick start

```python
import os

import ollie
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.plugins import openai
from ollie_integrations_livekit import attach_ollie


def lookup_weather(city: str) -> dict:
    """Look up weather for a city."""
    return {"temp_f": 72, "condition": "sunny", "city": city}


# 1. Ollie client (uses OLLIE_API_KEY and OLLIE_AGENT_ID from your environment)
client = ollie.Client()

# 2. Enable tracing for all AgentSession instances in this worker
attach_ollie(client, app_name="voice_support")


def build_agent() -> Agent:
    return Agent(
        instructions=(
            "You are a helpful voice assistant. "
            "When asked about weather, call lookup_weather with the city name."
        ),
        tools=[function_tool(lookup_weather)],
    )


async def entrypoint(ctx: JobContext):
    session = AgentSession(llm=openai.LLM(model="gpt-4.1-mini"))
    await session.start(agent=build_agent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

Set your Ollie credentials before running (provided when your account is provisioned):

```bash
export OLLIE_API_KEY="your-ollie-api-key"
export OLLIE_AGENT_ID="your-agent-id"
```

Ollie does not use your LiveKit, OpenAI, or other provider API keys. You configure those separately to run your agent, the same way you would without Ollie.

---

## What gets traced

Each `AgentSession` produces **one Trace**. Every user utterance becomes a **turn interaction**; STT, turn detection, agent, tools, TTS, and (when present) LLM land as **spans** under that turn (`events.spans` → warehouse `trace_spans`).

Ollie automatically captures:

- **Session** — `workflow` name (app), room, job ID, session timing
- **User turns** — each utterance as `turn_N` (`interaction_type: conversational`)
- **Speech-to-text** — span `type: stt` (transcripts when content capture is on)
- **Turn detection** — span `type: turn_detection`
- **Agent** — span `type: agent`
- **LLM** — promoted to span `type: llm` under the agent when `livekit.llm_start` / `livekit.llm_end` fire
- **Tool calls** — span `type: tool` (parented under the agent)
- **Text-to-speech** — span `type: tts`
- **Errors** — failed tools and failed sessions are marked with `success: false` / span `status: failure`

### Trace structure

| LiveKit stage | Warehouse layer | Wire field |
|---------------|-----------------|------------|
| Session lifetime | Trace + `workflow` | `workflow.name` = your `app_name` |
| User utterance | Interaction | `name: turn_N`, `interaction_type: conversational` |
| Speech-to-text | Span | `events.spans[]` `type: stt` |
| Turn detection | Span | `type: turn_detection` |
| Agent | Span | `type: agent` |
| LLM | Span | `type: llm` (under agent) |
| Tool | Span | `type: tool` |
| Text-to-speech | Span | `type: tts` |

Example for one voice turn with a tool call:

```
Trace / workflow: voice_support
└── Interaction turn_1 (conversational)
    ├── span stt
    ├── span turn_detection
    ├── span support_agent (agent)
    │   ├── span llm
    │   └── span lookup_weather (tool)
    └── span tts
```

---

## Configuration

### Auto-instrumentation (recommended)

Call `attach_ollie()` once at worker startup, before the first `AgentSession.start()`:

```python
attach_ollie(
    client,
    app_name="voice_support",   # root name in traces; defaults to OLLIE_LIVEKIT_APP_NAME or livekit_session
    flush_mode="ingest",        # default: send trace when session closes
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | Your `ollie.Client` instance |
| `app_name` | `livekit_session` | Name of the session `workflow` (not a separate interaction) |
| `flush_mode` | `ingest` | `ingest` (production), `validate` (schema check only), or `process` (preview) |

All `AgentSession` instances in the process are traced automatically after `attach_ollie()`.

### Content redaction

To trace pipeline structure and timing without transcripts or message text:

```bash
export LIVEKIT_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false
```

`input` and `output` fields will be empty. Traces still ingest successfully.

---

## Tool call tracking

When your agent calls tools during a session, each tool is a child interaction under the agent:

```python
@function_tool
async def lookup_reservation(confirmation: str) -> dict:
    return {"found": True, "confirmation": confirmation}

agent = Agent(
    instructions="Help users with reservations.",
    tools=[lookup_reservation],
)
```

Tool calls emit `livekit.tool_start` and `livekit.tool_end` (or `livekit.tool_error` on failure). Implement tools as `async def` when LiveKit requires awaitable handlers.

---

## Text input mode

For agents that accept text input (without room audio), drive a turn after `start()`:

```python
await session.start(agent=build_agent())
run_result = session.run(
    user_input="I need help with my reservation.",
    input_modality="text",
)
await run_result
await session.aclose()
```

Text-mode sessions may omit `stt` and `tts` interactions. Agent and tool interactions are still captured.

---

## Room attribution

When you pass a LiveKit `room` to `session.start(agent=agent, room=ctx.room)`, Ollie records `room` and `job_id` on the session (workflow / first-turn attributes).

---

## Captured fields

Turn interactions include `input`, `output`, `events` (`{trigger, context, spans}`), and `attributes`. Pipeline stages live on spans.

### Session (`workflow`)

| Field | Description |
|-------|-------------|
| `workflow.name` | App / room name from `attach_ollie(app_name=...)` |
| `workflow.status` / times | Session lifecycle |
| First-turn `events.context` | `livekit.session_started` / `livekit.session_ended` when present |
| Attributes | `room`, `job_id`, `session_id`, `latency_ms`, `success` |

### User turn (interaction)

| Field | Description |
|-------|-------------|
| `input` | Prefer STT transcript; else turn audio/text reference |
| `output` | Prefer agent reply text; else turn output reference |
| `events.spans` | STT / turn_detection / agent / tool / tts / llm spans |
| `attributes` | `latency_ms`, `success` |

### Stage spans (`events.spans[]`)

| `type` | Typical `input` / `output` |
|--------|----------------------------|
| `stt` | audio ref → final transcript |
| `turn_detection` | transcript → endpoint decision |
| `agent` | user text → agent reply |
| `llm` | (promoted from `livekit.llm_*` on agent) |
| `tool` | args → result |
| `tts` | reply text → audio ref |

Each span carries `status`, `span_ref`, optional `parent_span_ref`, and `properties` (`kind`, `name`, `status`, `duration_ms`, …).

Trace-level metadata includes `agent_id`, `session_id`, and `workflow.name` (your `app_name`).

---

## Retrieving the last trace

```python
from ollie_integrations_livekit import get_last_wire_payload

payload = get_last_wire_payload()
```

Returns the v2 payload from the most recently closed session. Useful for tests and debugging.

---

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | |
| Ollie API key and agent ID | From your Ollie account |
| `livekit-agents` >= 1.5 | Installed via `[agent]` extra |
| LiveKit and provider credentials | Your existing agent setup — not sent to Ollie |
