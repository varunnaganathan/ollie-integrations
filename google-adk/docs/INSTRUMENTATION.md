# Google ADK instrumentation

Automatic execution tracing for [Google ADK](https://github.com/google/adk-python) agents with Ollie.

Ollie hooks ADK’s native lifecycle (`Runner.run_async`, agent/tool/LLM instrumentation). Add two lines at startup; your agents, tools, and runners stay unchanged. No mapping YAML or OpenTelemetry setup.

---

## What it does

Each `Runner.run_async` call produces a normalized Ollie v2 trace with **one `run` interaction**:

| Wire layer | Role |
|------------|------|
| `run` | User input in, final answer out; all agent/tool/LLM spans in `events.spans` |

`events` is a dict with `trigger`, `context`, and `spans` (not a flat lifecycle list). Multi-agent topologies (sequential, parallel, loop, `sub_agents` delegation) use the same `attach_ollie()` call — no topology-specific code.

---

## Install

```bash
pip install ollie-sdk "ollie-integrations-google-adk[agent]"
```

The `[agent]` extra installs `google-adk` and `google-genai`.

**PyPI not available yet?** See [Install before PyPI](../INSTALL_BEFORE_PYPI.md).

If `ollie-sdk` is not on PyPI yet:

```bash
pip install "git+https://github.com/varunnaganathan/ollie-sdk.git@v0.1.0#egg=ollie-sdk"
pip install "ollie-integrations-google-adk[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.3#subdirectory=google-adk"
```

---

## Credentials

| Variable | Required | Notes |
|----------|----------|-------|
| `OLLIE_API_KEY` | Yes | From your Ollie account |
| `OLLIE_AGENT_ID` | Yes | Agent UUID from Ollie |
| `OLLIE_INGEST_BASE_URL` | Optional | Defaults to Ollie cloud ingest |
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Yes (for ADK) | Your Google/Gemini key — **not sent to Ollie** |

Ollie only receives normalized trace payloads after each run. Google credentials stay on your machine, same as running ADK without Ollie.

---

## Quick start

```python
import asyncio
import uuid

import ollie
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types
from ollie_integrations_google_adk import attach_ollie


def get_weather(city: str) -> dict:
  return {"temperature": 72, "condition": "sunny", "city": city}


APP_NAME = "weather_app"

client = ollie.Client()
attach_ollie(client, app_name=APP_NAME, flush_mode="ingest")

agent = LlmAgent(
    name="weather_assistant",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant that can check weather.",
    tools=[FunctionTool(get_weather)],
)

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)

user_msg = types.Content(role="user", parts=[types.Part(text="What's the weather in New York?")])


async def main():
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME,
        user_id="user-123",
        session_id=session_id,
    )
    async for event in runner.run_async(
        user_id="user-123",
        session_id=session_id,
        new_message=user_msg,
    ):
        if event.is_final_response():
            print(event.content.parts[0].text)


asyncio.run(main())
```

ADK 1.x requires `create_session()` before the first `run_async` for a new session id.

---

## Configuration

Call `attach_ollie()` once at process startup, before any `Runner.run_async`:

```python
attach_ollie(
    client,
    app_name="weather_app",
    flush_mode="ingest",
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | `ollie.Client()` instance |
| `app_name` | `adk_workflow` | Root `run` interaction name (`OLLIE_ADK_APP_NAME` env overrides) |
| `flush_mode` | `ingest` | `ingest` (production), `validate` (schema check only), `process` (preview) |

### Content redaction

```bash
export ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false
```

`input` and `output` are empty; structure, timing, and signals still ingest.

### Model selection

Set the Gemini model via ADK as usual. For the bundled sample agent:

```bash
export ADK_MODEL=gemini-2.5-flash
```

---

## Wire shape

Example — single agent with one tool call:

```
weather_app (run)
├── weather_assistant (span: agent)
├── get_weather (span: tool)
└── gemini-2.5-flash (span: llm)
```

Multi-agent delegation:

```
research_app (run)
├── orchestrator (span: agent)
├── researcher (span: agent, parent → orchestrator)
├── search_filings (span: tool, parent → researcher)
└── gemini-2.5-flash (span: llm, parent → researcher)
```

Trace metadata includes `agent_id`, `session_id`, and `workflow.name` (your `app_name`).

---

## Custom attributes

### Run / interaction (all versions with `add_interaction_attributes`)

Attach product metadata to the active **run** while `Runner.run` / `run_async` is in flight. Register non-built-in names once with `client.define_feature(...)` before ingest.

```python
from ollie_integrations_google_adk import add_interaction_attributes

client.define_feature(
    "user_tier",
    kind="observable",
    description="Customer plan tier at request time",
)

# During an active run:
add_interaction_attributes({"user_tier": "pro", "request_id": "req-1"})
```

Default target is `interaction="run"`. With **0.3.3+**, `interaction="agent"` also copies custom keys onto that agent span’s `properties`.

### Span properties (0.3.3+)

Attach metadata to the **current open span** (tool / llm / agent). No `define_feature` required — values land on span `properties`.

```python
from ollie_integrations_google_adk import add_span_attributes

# Inside a tool body (or while that span is open):
add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
```

Reserved keys (`kind`, `name`, `status`, tokens, …) cannot be overwritten. Auto-collected span properties still need no extra calls.

---

## Multi-agent workflows

`SequentialAgent`, `ParallelAgent`, `LoopAgent`, and `LlmAgent` with `sub_agents` are supported with the same instrumentation:

```python
from google.adk.agents import LlmAgent, SequentialAgent

researcher = LlmAgent(name="researcher", model="gemini-2.5-flash", tools=[search_tool])
writer = LlmAgent(name="writer", model="gemini-2.5-flash")
pipeline = SequentialAgent(name="pipeline", sub_agents=[researcher, writer])

runner = Runner(app_name="research_app", agent=pipeline, session_service=session_service)
# attach_ollie already called — each run_async emits one trace
```

---

## Verify before production

1. **Install** — follow [Install before PyPI](../INSTALL_BEFORE_PYPI.md) (GitHub) until PyPI is live. Use a **new** virtualenv; do not reuse your app venv for the install smoke test.
2. **Import check** (doc step 4):

```bash
python -c "import ollie; from ollie_integrations_google_adk import attach_ollie; print('ok')"
```

3. **Ingest health:** `curl -sS "$OLLIE_INGEST_BASE_URL/health"`
4. Start with `flush_mode="validate"` to check schema (no persistence).
5. Switch to `flush_mode="ingest"` when traces look correct.
6. Sample agent sweep (from package examples, after install):

```bash
for mode in single sequential parallel loop delegation; do
  python -m sample_adk_agent.run --mode "$mode" --flush-mode validate
done
```

7. For local debugging, read the last payload:

```python
from ollie_integrations_google_adk import get_last_wire_payload

payload = get_last_wire_payload()
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `SessionNotFoundError` | Call `session_service.create_session()` before `run_async` |
| Model quota / 429 | Use `gemini-2.5-flash` or set `ADK_MODEL`; reduce parallel runs |
| `google.adk` import error | `pip install "ollie-integrations-google-adk[agent]"` |
| Empty traces | Confirm `attach_ollie()` runs before `run_async`; check `flush_mode` |
| Redacted content | Expected when `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false` |

---

## Related docs

- [Hooks reference](HOOKS.md) — hook points and API
- [Execution model](EXECUTION_MODEL.md) — span types and signals
- [Ollie SDK onboarding](https://github.com/varunnaganathan/ollie-sdk/blob/main/docs/CLIENT_ONBOARDING.md)
