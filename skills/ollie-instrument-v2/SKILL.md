---
name: ollie-instrument-v2
description: Router skill — pick the Ollie integration pin for the agent stack, attach, verify a cloud trace; fetch versioned package INSTRUMENTATION.md for how-tos.
---

# Ollie instrumentation (v2 — router)

Use when onboarding with Ollie or adding tracing. This skill **routes**; it does not hold full how-tos.

**v1** (fat how-tos, unchanged): `skills/ollie-instrument/SKILL.md`

## Required environment

Do **not** invent credentials. Use onboarding / `.ollie/env.sh` / the customer-provided `OLLIE_API_KEY` and `OLLIE_AGENT_ID`.

```bash
export OLLIE_API_KEY="..."
export OLLIE_AGENT_ID="..."
```

## Agent loop

```text
1. Confirm OLLIE_API_KEY + OLLIE_AGENT_ID in the same env that runs the app
2. Detect stack → install the pin from the table below
3. Apply the smallest attach stub (custom SDK: tracing=true, all LLM providers)
4. Run one representative invocation with flush/ingest
5. Confirm cloud diagnose / dashboard shows a trace for that agent_id
```

Never mark done without a verified cloud trace.

Onboarding check: `flush_mode="validate"` (or `OLLIE_FLUSH_MODE=validate`). Production: `flush_mode="ingest"` / `flushIngest`.

**Before enrichment** (custom attributes, signals, multi-agent notes, troubleshooting): fetch the framework **INSTRUMENTATION.md** at the pin URL below. Do not invent APIs from memory.

## Current pins

| Framework | Install pin(s) | Docs (one per framework) |
|-----------|----------------|--------------------------|
| ollie-sdk (custom Py/TS) | `v0.3.2` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-sdk/v0.3.2/docs/INSTRUMENTATION.md) |
| Google ADK | `google-adk-v0.3.3` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/google-adk-v0.3.3/google-adk/docs/INSTRUMENTATION.md) |
| OpenAI Agents | Py `openai-agents-v0.2.3` · TS `openai-agents-ts-v0.2.2` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-v0.2.3/openai-agents/docs/INSTRUMENTATION.md) (identical file under `openai-agents-ts` at the TS tag) |

## Google ADK

Detect: `google.adk`, `LlmAgent`, `Runner.run_async` / `Runner.run`.

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
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
```

**Docs:** https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/google-adk-v0.3.3/google-adk/docs/INSTRUMENTATION.md  
(Version capabilities and enrichment — fetch the doc.)

## OpenAI Agents

Detect: `agents.Agent` / `@openai/agents`, `Runner.run` / `run_sync`.

**Python install:**

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.3#subdirectory=openai-agents"
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
# Once at startup, before Runner.run / run_sync.
```

**TypeScript install:**

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.2:openai-agents-ts"
npm install "github:varunnaganathan/ollie-sdk#v0.3.2:packages/ts"
```

```ts
import { RunCollector, collectorToWirePayload } from "@ollie/integrations-openai-agents";
// Populate RunCollector from your processor; see docs for attrs / emitSignal / flush.
```

**Docs (Python + TypeScript in one file):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-v0.2.3/openai-agents/docs/INSTRUMENTATION.md

## Custom Python / TypeScript (ollie-sdk)

Detect: direct OpenAI / Anthropic / Gemini SDK calls, or manual `client.workflow` / `tool` (no agent framework).

**Default onboarding:** always call `init` / `initAsync` with **`tracing=True` / `tracing: true`**. Do **not** pass a narrow `instruments` allowlist unless the customer asks — with the default, **OpenAI, Anthropic, and Gemini** client calls are all auto-captured as LLM / generation spans (OTEL). Install tracing peers for the languages in use. Custom non-LLM tools still need `ollie.tool` / `tool()`. Persist with `flush_ingest` / `flushIngest`.

**Python:**

```bash
pip install "ollie-sdk[tracing] @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
# Provider SDKs the app already uses (only those needed to run):
# pip install openai anthropic google-genai
```

```python
import ollie

# tracing=True → auto-instrument OpenAI + Anthropic + Gemini (all installed providers)
client = ollie.init(tracing=True)
with client.workflow(name="my_app", input=user_msg) as wf:
    # LLM SDK calls inside this workflow are captured automatically
    # Custom tools: with ollie.tool("name", input=...) as t: t.output = "..."
    wf.output = "..."
wf.flush_ingest()
```

**TypeScript:**

```bash
npm install "github:varunnaganathan/ollie-sdk#v0.3.2:packages/ts"
npm install @opentelemetry/api @opentelemetry/instrumentation \
  @opentelemetry/resources @opentelemetry/sdk-trace-node \
  @opentelemetry/instrumentation-openai \
  @traceloop/instrumentation-anthropic
# Provider SDKs the app uses, e.g. openai / @anthropic-ai/sdk / @google/genai
```

```ts
import { initAsync, tool } from "@ollie/sdk";

// tracing: true, no instruments allowlist → OpenAI + Anthropic + Gemini
// Must run BEFORE dynamic import() of provider SDKs
const client = await initAsync({ tracing: true });

const { default: OpenAI } = await import("openai");
// ... app LLM calls inside a workflow ...
const wf = client.workflow({ name: "my_app", input: userMsg });
wf.enter();
try {
  // LLM calls auto-captured; custom tools via tool()
  wf.output = "...";
} finally {
  wf.exit();
}
await wf.flushIngest();
await client.shutdown();
```

**Docs (Python + TypeScript in one file):**  
https://raw.githubusercontent.com/varunnaganathan/ollie-sdk/v0.3.2/docs/INSTRUMENTATION.md
