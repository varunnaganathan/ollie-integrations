# ADK hooks

## `attach_ollie`

```python
from ollie import Client
from ollie_integrations_google_adk import attach_ollie, get_last_wire_payload

client = Client()
attach_ollie(client, app_name="my_app", flush_mode="ingest")
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `client` | required | `ollie.Client` instance |
| `app_name` | `OLLIE_ADK_APP_NAME` or `adk_workflow` | Root `run` interaction name |
| `flush_mode` | `ingest` | `ingest`, `validate`, or `process` |
| `runner` | optional | Reserved for future runner-specific config |

Call once at process startup, before any `Runner.run_async` invocations.

## Hook points

| Hook | ADK symbol | Wire output |
|---|---|---|
| Run | `Runner.run_async` | `run` interaction (I/O, attributes) |
| Agent | `_instrumentation.record_agent_invocation` | `agent` span (delegation) |
| Tool | `_instrumentation.record_tool_execution` | `tool` span |
| LLM | `telemetry.tracing.trace_call_llm` | `llm` span (model id, tokens, finish_reason) |

ADK's built-in OTel export remains independent — Ollie hooks run in parallel.

## Content capture

When `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`, input/output are empty strings and an `adk.content_redacted` event may be emitted on the collector node. Ingest never fails due to redaction.

## Retrieving the last payload

```python
wire = get_last_wire_payload()
```

Useful for tests and `--dump-wire` CLI without hitting the ingest API.

## Live sample

```bash
pip install -e "integrations/google-adk[agent,dev]"
python -m examples.sample_adk_agent.run --mode single --dump-wire
```

Requires `GOOGLE_API_KEY`, `GOOGLE_GENAI_API_KEY`, or `GEMINI_API_KEY` in your environment.
