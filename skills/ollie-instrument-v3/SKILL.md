---
name: ollie-instrument-v3
description: Router skill with closed-loop onboarding — validate response check, diagnose until verified, poll UU issues until onboarding complete; never ask Ollie support whether traces landed.
---

# Ollie instrumentation (v3 — closed-loop router)

Use when onboarding with Ollie or adding tracing. This skill **routes** and **verifies end-to-end** until issues are back.

**v1** (fat how-tos, unchanged): `skills/ollie-instrument/SKILL.md`  
**v2** (router only, unchanged): `skills/ollie-instrument-v2/SKILL.md`

## Required environment

Do **not** invent credentials. Use onboarding / `.ollie/env.sh` / the customer-provided values.

```bash
export OLLIE_API_KEY="..."
export OLLIE_AGENT_ID="..."
export OLLIE_BASE_URL="${OLLIE_BASE_URL:-https://olliemainapi.onrender.com}"
export OLLIE_INGEST_BASE_URL="${OLLIE_INGEST_BASE_URL:-https://olliejudge-sentry-backend.onrender.com}"
```

(`OLLIE_CLOUD_INGEST_BASE_URL` is an alias for `OLLIE_INGEST_BASE_URL` if set.)

## Closed-loop onboarding (mandatory — once per setup)

**Do not ask the customer to check with Ollie support to learn whether traces landed — use the validate response body + diagnose.**

**Onboarding complete** only when `GET /issues/unknown-unknown` returns a **non-empty** issues list. Until then, report status as **in progress**.

```text
1. Confirm OLLIE_API_KEY + OLLIE_AGENT_ID (+ BASE / INGEST URLs) in the same env that runs the app
2. Detect stack → install the pin from the table below
3. Apply the smallest attach stub (custom SDK: tracing=true, all LLM providers)
4. VALIDATE: flush_mode=validate / OLLIE_FLUSH_MODE=validate — run one invocation
5. INSPECT VALIDATE RESPONSE BODY (HTTP 200 is not enough)
   - Require accepted: true (or batch result equivalent with no blocking errors)
   - If accepted false / errors → show the user the errors, fix, retry validate. Do NOT ingest yet.
6. INGEST: flush_mode=ingest — run one invocation
7. POLL DIAGNOSE until verified:true AND latest related sdk.trace.ingest status is completed (not failed)
8. If hint is validate_only_or_failed / events_received_but_no_trace / no_events,
   OR any recent_events[].last_error → show that text to the user, fix, re-run validate→ingest→diagnose
9. POLL UU issues until non-empty; while empty report interaction_count vs threshold + uu_onboarding
10. When issues appear → summarize, ask user if they want help fixing, point to dashboard
```

Never mark setup done while diagnose is not verified. Never mark **onboarding complete** while UU issues are empty.

### Curls (copy as written)

```bash
# After validate flush — parse JSON; require accepted (shape depends on SDK batch response)
# After ingest — poll until verified
curl -sS -H "X-API-Key: $OLLIE_API_KEY" \
  "$OLLIE_INGEST_BASE_URL/v1/sdk/onboarding/diagnose?agent_id=$OLLIE_AGENT_ID"

# Until onboarding complete (issues non-empty)
curl -sS -H "X-API-Key: $OLLIE_API_KEY" \
  "$OLLIE_BASE_URL/issues/unknown-unknown?status=active"
```

Diagnose fields to read: `verified`, `hint`, `trace_count`, `interaction_count`, `uu_onboarding`, `recent_events` (`event_type`, `status`, `last_error`, `session_id`).

HTTP 200 on `/v1/sdk/events/batch` does **not** mean a warehouse trace exists — always confirm with diagnose.

**Before enrichment** (custom attributes, signals, multi-agent notes, troubleshooting): fetch the framework **INSTRUMENTATION.md** at the pin URL below. Do not invent APIs from memory.

## Current pins

| Framework | Install pin(s) | Docs (one per framework) |
|-----------|----------------|--------------------------|
| ollie-sdk (custom Py/TS) | `v0.3.3` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-sdk/v0.3.3/docs/INSTRUMENTATION.md) |
| Google ADK | `google-adk-v0.3.3` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/google-adk-v0.3.3/google-adk/docs/INSTRUMENTATION.md) |
| OpenAI Agents | Py `openai-agents-v0.2.3` · TS `openai-agents-ts-v0.2.2` | [INSTRUMENTATION.md](https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-v0.2.3/openai-agents/docs/INSTRUMENTATION.md) (identical file under `openai-agents-ts` at the TS tag) |

## Google ADK

Detect: `google.adk`, `LlmAgent`, `Runner.run_async` / `Runner.run`.

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.3"
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

## OpenAI Agents

Detect: `agents.Agent` / `@openai/agents`, `Runner.run` / `run_sync`.

**Python install:**

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.3"
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
```

**TypeScript install:**

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.2:openai-agents-ts"
npm install "github:varunnaganathan/ollie-sdk#v0.3.3:packages/ts"
```

**Docs:** https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/openai-agents-v0.2.3/openai-agents/docs/INSTRUMENTATION.md

## Custom Python / TypeScript (ollie-sdk)

Detect: direct OpenAI / Anthropic / Gemini SDK calls, or manual `client.workflow` / `tool` (no agent framework).

**Default onboarding:** always call `init` / `initAsync` with **`tracing=True` / `tracing: true`**. Do **not** pass a narrow `instruments` allowlist unless the customer asks.

**Python:**

```bash
pip install "ollie-sdk[tracing] @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.3"
```

```python
import ollie

client = ollie.init(tracing=True)
with client.workflow(name="my_app", input=user_msg) as wf:
    wf.output = "..."
# Onboarding: validate first, then ingest (see closed-loop above)
wf.flush()          # or flush_mode=validate path per docs
wf.flush_ingest()   # after validate accepted
```

**TypeScript:**

```bash
npm install "github:varunnaganathan/ollie-sdk#v0.3.3:packages/ts"
npm install @opentelemetry/api @opentelemetry/instrumentation \
  @opentelemetry/resources @opentelemetry/sdk-trace-node \
  @opentelemetry/instrumentation-openai \
  @traceloop/instrumentation-anthropic
```

```ts
import { initAsync } from "@ollie/sdk";

const client = await initAsync({ tracing: true });
const wf = client.workflow({ name: "my_app", input: userMsg });
wf.enter();
try {
  wf.output = "...";
} finally {
  wf.exit();
}
await wf.flushIngest();
await client.shutdown();
```

**Docs:** https://raw.githubusercontent.com/varunnaganathan/ollie-sdk/v0.3.3/docs/INSTRUMENTATION.md

## Dashboard

After diagnose `verified`, point the user at `https://{slug}.tryollie.com/data` (Trajectories) and `/issues` once UU issues appear.
