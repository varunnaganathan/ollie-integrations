/**
 * Synthetic sample: exercise all OpenAI Agents TS instrumentation APIs
 * and print the wire payload (no OpenAI key required).
 *
 * Run from package root:
 *   npx tsx examples/sample_capabilities.ts
 *   # or after build: node --import tsx examples/sample_capabilities.ts
 */
import {
  addInteractionAttributes,
  addSpanAttributes,
  collectorToWirePayload,
  emitSignal,
  RunCollector,
} from "../src/index.js";
import { warehouseShapeSpan } from "../src/warehouseSpan.js";

function main(): void {
  const c = new RunCollector({
    workflowName: "sample_oa_ts_caps",
    sessionId: "sess-caps",
    inputText: "What's the weather in NYC?",
  });

  RunCollector.runWith(c, () => {
    addInteractionAttributes({ user_tier: "pro", request_id: "req-e2e-1" });
    emitSignal("refund_requested", { kind: "context" });

    c.pushOpenSpan("sp_tool_1");
    addSpanAttributes({ vendor: "core_ledger", retry_count: 0 });
    emitSignal("tool_slow_path", { kind: "context" });
    c.addSpan(
      warehouseShapeSpan({
        type: "tool",
        name: "get_weather",
        status: "success",
        span_ref: "sp_tool_1",
        duration_ms: 12,
        input: { text: "NYC" },
        output: { text: "72F sunny" },
      }),
    );
    c.popOpenSpan("sp_tool_1");
    c.close("It's 72°F and sunny in NYC.", true);
  });

  const wire = collectorToWirePayload(c, "agent_oa_ts_caps");
  console.log(JSON.stringify(wire, null, 2));
}

main();
