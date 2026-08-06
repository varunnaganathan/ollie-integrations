# OpenAI Agents SDK (TypeScript) instrumentation

Wire-format library for Ollie v2 ingest with the OpenAI Agents SDK.

## Install

When published:

```bash
npm install @ollie/integrations-openai-agents @openai/agents ollie-sdk
```

**npm not available yet?** See [../docs/customers/install-before-pypi.md](../docs/customers/install-before-pypi.md).

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.1:openai-agents-ts"
```

## Version capabilities

| Package version | `addInteractionAttributes` | `addSpanAttributes` | `emitSignal` |
|-----------------|----------------------------|---------------------|--------------|
| `<=0.2.0` | No | No | No |
| `0.2.1+` | Yes (`defineFeature`) | Yes (open span) | Yes (`_signal_hits`) |

## Custom instrumentation

```ts
import {
  RunCollector,
  addInteractionAttributes,
  addSpanAttributes,
  emitSignal,
  collectorToWirePayload,
} from "@ollie/integrations-openai-agents";

const c = new RunCollector({ workflowName: "support", inputText: "hello" });
RunCollector.runWith(c, () => {
  addInteractionAttributes({ user_tier: "pro" });
  c.pushOpenSpan("sp_tool_1");
  addSpanAttributes({ vendor: "core_ledger" });
  emitSignal("refund_requested", { kind: "context" });
  // … addSpan(warehouseShapeSpan({…})) then popOpenSpan
  c.close("done", true);
});
const wire = collectorToWirePayload(c, agentId);
```

## Verify

Synthetic e2e (no API key):

```bash
npm test -- tests/e2e-capabilities.test.ts
```

Sample wire dump:

```bash
npx tsx examples/sample_capabilities.ts
```
