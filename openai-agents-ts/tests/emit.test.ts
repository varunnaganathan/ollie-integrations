import { describe, expect, it } from "vitest";
import { RunCollector } from "../src/collector.js";
import { collectorToWirePayload } from "../src/emit.js";

describe("single-run wire", () => {
  it("emits one run interaction", () => {
    const c = new RunCollector({
      workflowName: "assistant",
      inputText: "hello",
    });
    c.addSpan({ type: "tool", name: "get_weather", status: "success", span_ref: "sp_tool_1" });
    c.close("hi", true);
    const wire = collectorToWirePayload(c, "agent_1");
    expect(wire.interactions).toHaveLength(1);
    const ix = wire.interactions[0];
    expect(ix.interaction_type).toBe("run");
    expect(typeof ix.input).toBe("string");
    expect(ix.events.trigger).toEqual([]);
    expect(ix.events.context).toEqual([]);
    expect(Array.isArray(ix._signal_hits)).toBe(true);
    expect(ix._signal_hits.some((h) => h.signal === "used_tool")).toBe(true);
    for (const span of ix.events.spans) {
      expect(typeof span.properties).toBe("object");
      expect(typeof span.input).toBe("object");
      expect(typeof span.output).toBe("object");
    }
  });
});
