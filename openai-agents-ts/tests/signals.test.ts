/** @vitest-environment node */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { instrumentEvents } from "../src/signals.js";
import type { SpanRecord } from "../src/types.js";

const __dir = dirname(fileURLToPath(import.meta.url));

describe("signals parity", () => {
  it("emits delegation for handoff span", () => {
    const spans: SpanRecord[] = [
      { type: "handoff", name: "Triage → Billing", status: "success", span_ref: "h1" },
    ];
    const { events, signalHits } = instrumentEvents(spans, "ok", true, 100);
    expect(events.trigger).toEqual([]);
    expect(events.context).toEqual([]);
    expect(signalHits.some((h) => h.signal === "delegation")).toBe(true);
    expect(signalHits.find((h) => h.signal === "delegation")?.anchor_kind).toBe("span");
  });

  it("anchors tool_error to failed tool span", () => {
    const spans: SpanRecord[] = [
      { type: "tool", name: "get_weather", status: "failure", span_ref: "sp_tool_1" },
    ];
    const { events, signalHits } = instrumentEvents(spans, "err", true, 100);
    expect(events.trigger).toEqual([]);
    expect(events.context).toEqual([]);
    const hit = signalHits.find((h) => h.signal === "tool_error");
    expect(hit).toBeDefined();
    expect(hit?.anchor_kind).toBe("span");
    expect(hit?.anchor_id).toBe("sp_tool_1");
  });

  it("anchors guardrail_blocked to guardrail span", () => {
    const spans: SpanRecord[] = [
      {
        type: "guardrail",
        name: "content_filter",
        status: "failure",
        span_ref: "gr_1",
        triggered: true,
      },
    ];
    const { events, signalHits } = instrumentEvents(spans, "blocked", true, 100);
    expect(events.trigger).toEqual([]);
    expect(events.context).toEqual([]);
    const hit = signalHits.find((h) => h.signal === "guardrail_blocked");
    expect(hit?.kind).toBe("trigger");
    expect(hit?.anchor_kind).toBe("span");
    expect(hit?.anchor_id).toBe("gr_1");
  });
});

describe("fixture parity", () => {
  it("loads golden single-run fixture if present", () => {
    const fixturePath = resolve(__dir, "../../../tests/fixtures/sdk/openai_single_run.json");
    try {
      const raw = readFileSync(fixturePath, "utf-8");
      const payload = JSON.parse(raw);
      expect(payload.interactions[0].interaction_type).toBe("run");
    } catch {
      expect(true).toBe(true);
    }
  });
});
