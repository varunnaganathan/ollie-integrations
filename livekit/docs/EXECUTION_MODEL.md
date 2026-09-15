# LiveKit execution model → Ollie v2

LiveKit Agents coordinate STT, turn detection, LLM, tools, and TTS inside an `AgentSession`. Ollie maps that to the warehouse grain used by ADK and custom Python:

| Warehouse layer | Unit | Source |
|---|---|---|
| **Trace** | Whole `AgentSession` | `session_id` + `workflow` |
| **Interaction** | One `user_turn` (`turn_N`) | User utterance → agent reply |
| **Span** | STT / turn detection / agent / tool / TTS / LLM | Children of that turn (`events.spans` → `trace_spans`) |

`agent_session` is **workflow metadata**, not its own interaction row.

## Node → wire mapping

| LiveKit source | Wire location | Notes |
|---|---|---|
| `AgentSession.start` → `close` | `workflow` | name / status / times |
| User utterance | interaction `turn_N` | `interaction_type: conversational` |
| Speech-to-text | span `type: stt` | under the turn |
| VAD / semantic endpoint | span `type: turn_detection` | under the turn |
| Agent loop | span `type: agent` | under the turn |
| Tool call | span `type: tool` | `parent_span_ref` → agent |
| Text-to-speech | span `type: tts` | under the turn |
| LLM start/end events | span `type: llm` | promoted under the agent span when `livekit.llm_*` events exist |

## Example shape (one voice turn with a tool)

```
Trace (AgentSession / workflow)
└── Interaction turn_1 (conversational)
    ├── span stt
    ├── span turn_detection
    ├── span support_agent (agent)
    │   ├── span llm
    │   └── span lookup_weather (tool)
    └── span tts
```

## vs ADK

| ADK | LiveKit |
|---|---|
| workflow → one `run` interaction + agent/tool/llm spans | workflow → one interaction **per turn** + voice/agent/tool/llm spans |
| LLM as child span | LLM promoted to `llm` span under agent when events present |
| Text-first | Voice pipeline stages are first-class span types |
