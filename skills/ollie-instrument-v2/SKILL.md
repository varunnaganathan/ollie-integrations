---
name: ollie-instrument-v2
description: Router skill — pick the Ollie integration pin for the agent stack, attach, verify a cloud trace; fetch versioned package INSTRUMENTATION.md for how-tos.
---

# Ollie instrumentation (v2 — router)

Use when onboarding with Ollie or adding tracing. This skill **routes**; it does not hold full how-tos.

**v1** (fat how-tos, unchanged): `skills/ollie-instrument/SKILL.md`

## Required environment

Do **not** invent credentials. Use onboarding / `.ollie/env.sh` / the customer.

```bash
export OLLIE_API_KEY="..."
export OLLIE_AGENT_ID="..."
```

`create_ollie_client()` / `ollie.Client()` read these from the environment.

## Agent loop

```text
1. Confirm OLLIE_API_KEY + OLLIE_AGENT_ID in the same env that runs the app
2. Detect stack → install the pin from the table below
3. Apply the smallest attach stub
4. Run one representative invocation
5. Confirm cloud diagnose / dashboard shows a trace for that agent_id
```

Never mark done without a verified cloud trace.

Onboarding check: `flush_mode="validate"` (or `OLLIE_FLUSH_MODE=validate`). Production: `flush_mode="ingest"`.

**Before optional enrichment** (custom attributes, signals, multi-agent notes, troubleshooting): fetch the package docs at the **pin tag** (URLs below). Do not invent APIs from memory.

## Current pins

| Package | Tag / pin |
|---------|-----------|
| ollie-sdk (Python + TS) | `v0.3.1` |
| Google ADK | `google-adk-v0.3.3` |
| OpenAI Agents (Python) | `openai-agents-v0.2.2` |
| OpenAI Agents (TypeScript) | `openai-agents-ts-v0.2.1` |

## Google ADK

Detect: `google.adk`, `LlmAgent`, `Runner.run_async` / `Runner.run`.

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.1"
pip install "ollie-integrations-google-adk[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.3#subdirectory=google-adk"
```

Also need `GOOGLE_API_KEY` or `GEMINI_API_KEY` (not sent to Ollie).

```python
import os
from ollie_integrations_google_adk import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(
    client,
    app_name="my_adk_app",  # same string as Runner(app_name=...)
    flush_mode=os.getenv("OLLIE_FLUSH_MODE", "ingest"),
)
# Once at startup, before first Runner.run / run_async.
# Keep create_session → run / run_async. Do not wrap Runner yourself.
```

**Docs (required for anything beyond attach):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/google-adk-v0.3.3/google-adk/docs/INSTRUMENTATION.md

Capability pointers (details in docs): run attrs via `add_interaction_attributes`; span attrs on **0.3.3+** via `add_span_attributes`.

## OpenAI Agents (Python)

Detect: `agents.Agent`, `Runner.run` / `run_sync`, `openai-agents` (Python).

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.1"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.2#subdirectory=openai-agents"
```

```python
import os
from ollie_integrations_openai_agents import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(
    client,
    workflow_name="my_openai_agent",
    flush_mode=os.getenv("OLLIE_FLUSH_MODE", "ingest"),
)
# Once at startup, before Runner.run / run_sync. Keep real Runner path.
```

**Docs (required for anything beyond attach):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-v0.2.2/openai-agents/docs/INSTRUMENTATION.md

Capability pointers (details in docs): run + span attrs on **0.2.2+** (`add_interaction_attributes`, `add_span_attributes`).

## OpenAI Agents (TypeScript)

Detect: `@openai/agents`, `Agent`, `Runner.run` in TypeScript/Node.

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.1:openai-agents-ts"
npm install "github:varunnaganathan/ollie-sdk#v0.3.1:packages/ts"
```

Wire-format package: populate `RunCollector` from your processor / run wrapper (each span needs `span_ref`), then `collectorToWirePayload` / `flushCollectorToClient`.

```ts
import {
  RunCollector,
  addInteractionAttributes,
  addSpanAttributes,
  emitSignal,
  collectorToWirePayload,
} from "@ollie/integrations-openai-agents";

const collector = new RunCollector({ workflowName: "my_openai_agent", inputText: userMsg });
RunCollector.runWith(collector, () => {
  addInteractionAttributes({ user_tier: "pro" });
  // pushOpenSpan → addSpanAttributes / emitSignal → addSpan → popOpenSpan → close
});
const wire = collectorToWirePayload(collector, process.env.OLLIE_AGENT_ID!);
```

**Docs (required for anything beyond the stub):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-ts-v0.2.1/openai-agents-ts/docs/INSTRUMENTATION.md

Capability pointers on **0.2.1+**: `addInteractionAttributes`, `addSpanAttributes`, `emitSignal`.

## Custom Python / TypeScript (ollie-sdk)

Detect: direct OpenAI/Anthropic/Gemini calls, or manual `client.workflow` / `ollie.tool` (no agent framework).

**Python install:**

```bash
pip install "ollie-sdk[tracing] @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.1"
```

**TypeScript install:**

```bash
npm install "github:varunnaganathan/ollie-sdk#v0.3.1:packages/ts"
```

Minimal Python stub:

```python
import ollie

client = ollie.init(tracing=True)  # or Client() + workflow only
with client.workflow(name="my_app", input=user_msg) as wf:
    # LLM calls auto-captured when tracing=True; custom tools via ollie.tool
    wf.output = "..."
# Persist: wf.flush_ingest()
```

**Docs (required for enrichment):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-sdk/v0.3.1/docs/CLIENT_ONBOARDING.md

Capability pointers on **v0.3.1+** (details in docs):

- Interaction attrs: `ix.attribute` / `define_feature`
- Span props: `span_attribute` / `spanAttribute`
- Emit signals on a run: `signal` / `emit_signal` (`define_signal` = catalog only)
