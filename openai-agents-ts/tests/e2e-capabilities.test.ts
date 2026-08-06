import { describe, expect, it } from "vitest";

import {
  addInteractionAttributes,
  addSpanAttributes,
  collectorToWirePayload,
  emitSignal,
  RunCollector,
} from "../src/index.js";
import { warehouseShapeSpan } from "../src/warehouseSpan.js";

function assertFiveCapabilities(wire: ReturnType<typeof collectorToWirePayload>): void {
  expect(wire.schema_version).toBe(2);
  const ix = wire.interactions[0]!;
  const attrs = Object.fromEntries(ix.attributes.map((a) => [a.name, a.value]));
  expect(attrs.user_tier).toBe("pro");
  expect(attrs.request_id).toBe("req-e2e-1");

  const tool = ix.events.spans.find((s) => s.type === "tool" || s.properties?.kind === "tool");
  expect(tool).toBeTruthy();
  expect(tool!.properties?.vendor).toBe("core_ledger");
  expect(tool!.properties?.kind).toBe("tool");
  expect(tool!.name).toBeTruthy();

  const names = new Set(ix._signal_hits.map((h) => h.signal));
  expect(names.has("refund_requested")).toBe(true);
}

describe("e2e capabilities (synthetic)", () => {
  it("covers interaction attrs, span attrs, emitSignal, spans, signal hits", () => {
    const c = new RunCollector({
      workflowName: "e2e_oa_caps",
      sessionId: "sess-caps",
      inputText: "weather NYC?",
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

    const wire = collectorToWirePayload(c, "agent_e2e_caps");
    assertFiveCapabilities(wire);
    const names = new Set(wire.interactions[0]!._signal_hits.map((h) => h.signal));
    expect(names.has("tool_slow_path")).toBe(true);
  });
});
