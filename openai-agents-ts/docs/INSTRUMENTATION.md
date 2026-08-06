# OpenAI Agents instrumentation

One guide for **Python** and **TypeScript**. Install the language pin you need; enrichment APIs are documented per language below.

## Credentials

| Variable | Required | Notes |
|----------|----------|-------|
| `OLLIE_API_KEY` | Yes | From Ollie onboarding / `.ollie/env.sh` |
| `OLLIE_AGENT_ID` | Yes | Agent id from Ollie |
| `OPENAI_API_KEY` | Yes (for live runs) | Stays on your machine — not sent to Ollie |
| `OLLIE_BASE_URL` | Prod | Analysis / registry |
| `OLLIE_INGEST_BASE_URL` | Prod | Event ingest |

## Version capabilities

| Language | Package pin | Run / interaction attrs | Span attrs | User emit signal |
|----------|-------------|-------------------------|------------|------------------|
| Python | `<=0.2.1` | No | No | No |
| Python | `0.2.2` | Yes (`define_feature`) | Yes | No |
| Python | `0.2.3+` (`openai-agents-v0.2.3`) | Yes | Yes | Yes (`emit_signal`) |
| TypeScript | `<=0.2.0` | No | No | No |
| TypeScript | `0.2.1+` (`openai-agents-ts-v0.2.1` / `v0.2.2`) | Yes | Yes | Yes (`emitSignal`) |

Wire shape is the same in both languages: one `run` interaction per workflow invocation, warehouse `events.spans` + `_signal_hits`.

---

## Python

### Install

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.3#subdirectory=openai-agents"
```

When PyPI is available: `pip install ollie-sdk "ollie-integrations-openai-agents[agent]"`.

### Quick start

```python
import os
from agents import Agent, Runner, function_tool
from ollie_integrations_openai_agents import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(
    client,
    workflow_name="support_bot",
    flush_mode=os.getenv("OLLIE_FLUSH_MODE", "ingest"),
)

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

agent = Agent(name="Assistant", tools=[get_weather], instructions="Be helpful.")
result = Runner.run_sync(agent, "Weather in Paris?")
```

Call `attach_ollie` once at startup before `Runner.run` / `run_sync`. Keep the real Runner path.

### Custom attributes and signals

```python
from ollie_integrations_openai_agents import (
    add_interaction_attributes,
    add_span_attributes,
    emit_signal,
)

client.define_feature(
    "user_tier",
    kind="observable",
    description="Customer plan tier at request time",
)
# Optional catalog:
client.define_signal("refund_requested", kind="context", description="User asked for a refund")

@function_tool
def get_balance(account_id: str) -> dict:
    add_interaction_attributes({"user_tier": "pro", "request_id": "req-1"})
    add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
    emit_signal("refund_requested", kind="context")
    return {"balance": 10}
```

Call `add_span_attributes` / `emit_signal` while the tool (or other) span is open. Reserved span keys (`kind`, `name`, `status`, …) cannot be overwritten. Hits land in `_signal_hits` with auto signals (`used_tool`, …).

### Verify

```python
from ollie_integrations_openai_agents import get_last_wire_payload
print(get_last_wire_payload())
```

Start with `flush_mode="validate"`, then `"ingest"`.

Sample: `python examples/sample_openai_agent/run.py --mode capabilities`

---

## TypeScript

TypeScript is a **wire-format** package: populate `RunCollector` from your processor / run wrapper (each span needs `span_ref`), then flush. Python’s `attach_ollie` auto-processor is not mirrored yet.

### Install

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.2:openai-agents-ts"
npm install "github:varunnaganathan/ollie-sdk#v0.3.2:packages/ts"
```

### Quick start

```typescript
import {
  RunCollector,
  addInteractionAttributes,
  addSpanAttributes,
  emitSignal,
  collectorToWirePayload,
  flushCollectorToClient,
} from "@ollie/integrations-openai-agents";

const collector = new RunCollector({
  workflowName: "support_bot",
  inputText: "Weather in Paris?",
});

RunCollector.runWith(collector, () => {
  addInteractionAttributes({ user_tier: "pro", request_id: "req-1" });
  collector.pushOpenSpan("sp_tool_1");
  addSpanAttributes({ vendor: "core_ledger", retry_count: 0 });
  emitSignal("refund_requested", { kind: "context" });
  collector.addSpan({
    type: "tool",
    name: "get_weather",
    status: "success",
    span_ref: "sp_tool_1",
    duration_ms: 120,
  });
  collector.popOpenSpan("sp_tool_1");
  collector.close("It's 72°F in Paris.", true);
});

const wire = collectorToWirePayload(collector, process.env.OLLIE_AGENT_ID!);
// await flushCollectorToClient(collector, ollieClient, "validate");
```

### Verify

```bash
npm test -- tests/e2e-capabilities.test.ts
npx tsx examples/sample_capabilities.ts
```
