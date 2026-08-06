# OpenAI Agents execution model

One **`run`** interaction per `Runner.run()` / `Runner.run_sync()`.

| Interaction | Boundary | input | output |
|-------------|----------|-------|--------|
| `run` | `run()` called → returns | `run()` input (str or JSON) | `RunResult.final_output` (str) |

Handoffs, tools, LLMs, agents, guardrails, custom → **`events.spans`** on the same `run` (never a separate interaction).

Structural spans (`agent`, `handoff`, `guardrail`): **name** (and status / handoff endpoints / `triggered`) only — **input/output stay `{}`**. Conversation text lives on the `run` interaction and on `tool` / `llm` spans when the SDK provides it.

SDK `turn` / `task` hierarchy spans are not mapped.

See [WORKFLOW_INTERACTION_MODEL.md](../WORKFLOW_INTERACTION_MODEL.md).
