# LiveKit hooks

## `attach_ollie`

```python
from ollie import Client
from ollie_integrations_livekit import attach_ollie, get_last_wire_payload

client = Client()
attach_ollie(client, app_name="support_voice", flush_mode="ingest")
```

Call once at process startup before any `AgentSession.start()`.

## Event wiring

| LiveKit event | Ollie node |
|---|---|
| `AgentSession.start()` | open `agent_session` |
| `close` | close session, flush wire |
| `user_input_transcribed` (partial/final) | `stt` span + transcript events |
| `user_state_changed` / turn complete | `turn_detection` |
| LLM / agent activity | `agent` (+ `llm_start`/`llm_end` events) |
| `function_tools_executed` | `tool` |
| `speech_created` + done | `tts` |

## Content capture

When `LIVEKIT_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`, input/output are empty and a `livekit.content_redacted` event is emitted.

## Retrieving payload

```python
wire = get_last_wire_payload()
```
