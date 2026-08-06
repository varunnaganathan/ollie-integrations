import { hitsFromNamedSignals } from "./hits.js";
import type { EventsDict, SignalHit, SpanRecord } from "./types.js";

const SAFETY_FINISH = new Set(["safety", "content_filter", "content_filtered"]);
const TRUNCATED_FINISH = new Set(["length", "max_tokens", "max_output_tokens"]);

function dedupe(signals: Array<{ name: string; [k: string]: unknown }>) {
  const seen = new Set<string>();
  return signals.filter((s) => {
    if (seen.has(s.name)) return false;
    seen.add(s.name);
    return true;
  });
}

function directSignals(spans: SpanRecord[]) {
  const trigger: Array<{ name: string; [k: string]: unknown }> = [];
  const context: Array<{ name: string; [k: string]: unknown }> = [];

  for (const span of spans) {
    if (span.type === "handoff") {
      context.push({ name: "delegation" });
    } else if (span.type === "guardrail" && (span.status === "failure" || span.triggered)) {
      trigger.push({ name: "guardrail_blocked", guardrail: span.name });
    } else if (span.type === "tool" && span.status === "failure") {
      context.push({ name: "tool_error", tool: span.name });
    } else if (span.type === "llm" && span.status === "failure") {
      context.push({ name: "llm_error", llm: span.name });
    } else if (span.type === "llm") {
      const props =
        span.properties && typeof span.properties === "object" ? span.properties : {};
      const fr = String(span.finish_reason ?? props.finish_reason ?? "").toLowerCase();
      if (TRUNCATED_FINISH.has(fr)) context.push({ name: "output_truncated" });
      else if (SAFETY_FINISH.has(fr)) context.push({ name: "safety_stop" });
    }
  }

  return { trigger, context: dedupe(context) };
}

function derivedSignals(
  spans: SpanRecord[],
  output: string,
  success: boolean,
  latencyMs: number,
) {
  const trigger: Array<{ name: string; [k: string]: unknown }> = [];
  const context: Array<{ name: string; [k: string]: unknown }> = [];

  if (!success) context.push({ name: "runtime_failure" });
  if (!output.trim()) context.push({ name: "empty_final_response" });
  if (spans.some((s) => s.type === "tool")) context.push({ name: "used_tool" });
  const failedTools = spans.filter((s) => s.type === "tool" && s.status === "failure");
  if (failedTools.length >= 2) trigger.push({ name: "repeated_tool_error" });
  if (spans.filter((s) => s.type === "handoff").length >= 2)
    context.push({ name: "multi_handoff" });
  const threshold = Number(process.env.OLLIE_HIGH_LATENCY_MS ?? 30000);
  if (latencyMs >= threshold) context.push({ name: "high_latency" });

  return { trigger, context: dedupe(context) };
}

export function instrumentEvents(
  spans: SpanRecord[],
  output: string,
  success: boolean,
  latencyMs: number,
  interactionRef = "ix_0",
): { events: EventsDict; signalHits: SignalHit[] } {
  const { trigger: trigD, context: ctxD } = directSignals(spans);
  const { trigger: trigB, context: ctxB } = derivedSignals(spans, output, success, latencyMs);
  const trigger = dedupe([...trigD, ...trigB]);
  const context = dedupe([...ctxD, ...ctxB]);
  const signalHits = hitsFromNamedSignals({
    trigger,
    context,
    spans,
    interactionRef,
  });
  return {
    events: { trigger: [], context: [], spans },
    signalHits,
  };
}
