import { RunCollector } from "./collector.js";
import { makeSignalHit } from "./hits.js";
import { instrumentEvents } from "./signals.js";
import type { SignalHit, WirePayload } from "./types.js";
import { warehouseShapeSpans } from "./warehouseSpan.js";

const VERSION = "0.2.2";
const MAX_WIRE_CHARS = 32_000;

function truncate(text: string | null | undefined): [string, boolean] {
  if (text == null) return ["", false];
  const s = String(text);
  if (s.length <= MAX_WIRE_CHARS) return [s, false];
  return [s.slice(0, MAX_WIRE_CHARS) + "…[truncated]", true];
}

export function collectorToWirePayload(
  collector: RunCollector,
  agentId: string,
  sessionId?: string,
): WirePayload {
  const success = collector.status !== "failed";
  const interactionRef = "ix_0";
  const shapedSpans = warehouseShapeSpans(collector.spans);
  const { events, signalHits } = instrumentEvents(
    shapedSpans,
    collector.outputText,
    success,
    collector.latencyMs,
    interactionRef,
  );

  const [input, inpTrunc] = truncate(collector.inputText);
  const [output, outTrunc] = truncate(collector.outputText);

  const pending: SignalHit[] = [...signalHits];
  const seen = new Set(
    pending.map((h) => `${h.signal}|${h.kind}|${h.anchor_kind}|${h.anchor_id}`),
  );
  for (const h of collector.userSignalHits) {
    const k = `${h.signal}|${h.kind}|${h.anchor_kind}|${h.anchor_id}`;
    if (!h.signal || seen.has(k)) continue;
    seen.add(k);
    pending.push(h);
  }
  if (inpTrunc && !seen.has(`input_truncated|context|interaction|${interactionRef}`)) {
    pending.push(
      makeSignalHit({
        signal: "input_truncated",
        kind: "context",
        anchorKind: "interaction",
        anchorId: interactionRef,
      }),
    );
  }
  if (outTrunc && !seen.has(`output_truncated|context|interaction|${interactionRef}`)) {
    pending.push(
      makeSignalHit({
        signal: "output_truncated",
        kind: "context",
        anchorKind: "interaction",
        anchorId: interactionRef,
      }),
    );
  }

  if (!input.trim() && !output.trim()) {
    throw new Error("interaction requires at least one non-empty input or output string");
  }

  const attributes: Array<{ name: string; value: unknown }> = [
    { name: "latency_ms", value: collector.latencyMs },
    { name: "success", value: success },
  ];
  for (const [name, value] of Object.entries(collector.runAttributes)) {
    const key = String(name ?? "").trim();
    if (!key || key === "latency_ms" || key === "success") continue;
    attributes.push({ name: key, value });
  }

  const ended = collector.endedAt ?? collector.startedAt;
  return {
    schema_version: 2,
    sdk: { name: "ollie-integrations-openai-agents-ts", version: VERSION },
    agent_id: agentId,
    session_id: sessionId ?? collector.sessionId ?? agentId,
    workflow: {
      name: collector.workflowName,
      status: collector.status,
      started_at: collector.startedAt,
      ended_at: ended,
    },
    interactions: [
      {
        interaction_ref: interactionRef,
        parent_interaction_ref: null,
        interaction_type: "run",
        name: collector.workflowName,
        input,
        output,
        events: { trigger: [], context: [], spans: events.spans },
        _signal_hits: pending,
        attributes,
        started_at: collector.startedAt,
        ended_at: ended,
      },
    ],
  };
}

export async function flushCollectorToClient(
  collector: RunCollector,
  client: import("./types.js").OllieClient,
  flushMode = "ingest",
): Promise<unknown> {
  const payload = collectorToWirePayload(collector, client.agent_id, collector.sessionId);
  const mode = flushMode.toLowerCase();
  if (mode === "validate") return client._transport.validate_trace(payload, client._delivery);
  if (mode === "process") return client._transport.process_trace(payload, client._delivery);
  return client._transport.ingest_trace(payload, client._delivery);
}
