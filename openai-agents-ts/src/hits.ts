import type { SignalHit, SpanRecord } from "./types.js";

export type AnchorKind = "span" | "interaction";

const SPAN_ANCHORED = new Set([
  "tool_error",
  "llm_error",
  "delegation",
  "safety_stop",
  "output_truncated",
  "guardrail_blocked",
]);

export function makeSignalHit(opts: {
  signal: string;
  kind: string;
  anchorKind: AnchorKind;
  anchorId: string;
}): SignalHit {
  return {
    signal: opts.signal.trim(),
    kind: opts.kind.trim(),
    anchor_kind: opts.anchorKind,
    anchor_id: opts.anchorId.trim(),
  };
}

export function hitsFromNamedSignals(opts: {
  trigger: Array<{ name: string; [k: string]: unknown }>;
  context: Array<{ name: string; [k: string]: unknown }>;
  spans: SpanRecord[];
  interactionRef: string;
}): SignalHit[] {
  const { trigger, context, spans, interactionRef } = opts;
  const spansByName = new Map<string, SpanRecord[]>();
  for (const sp of spans) {
    const n = String(sp.name ?? "").trim();
    if (n) {
      const list = spansByName.get(n) ?? [];
      list.push(sp);
      spansByName.set(n, list);
    }
  }

  const pending: SignalHit[] = [];
  const seen = new Set<string>();

  const append = (sig: { name: string; [k: string]: unknown }, kind: string) => {
    const name = String(sig.name ?? "").trim();
    if (!name || seen.has(name)) return;
    seen.add(name);

    let anchorKind: AnchorKind = "interaction";
    let anchorId = interactionRef;

    if (SPAN_ANCHORED.has(name)) {
      anchorKind = "span";
      anchorId = "";

      if (name === "tool_error") {
        const tool = String(sig.tool ?? "").trim();
        const candidates =
          spansByName.get(tool) ??
          spans.filter((s) => s.type === "tool" && s.status === "failure");
        for (const sp of candidates) {
          anchorId = String(sp.span_ref ?? "");
          if (anchorId) break;
        }
      } else if (name === "llm_error") {
        const llm = String(sig.llm ?? "").trim();
        const candidates =
          spansByName.get(llm) ??
          spans.filter((s) => s.type === "llm" && s.status === "failure");
        for (const sp of candidates) {
          anchorId = String(sp.span_ref ?? "");
          if (anchorId) break;
        }
      } else if (name === "delegation") {
        for (const sp of spans) {
          if (sp.type === "handoff") {
            anchorId = String(sp.span_ref ?? "");
            if (anchorId) break;
          }
        }
      } else if (name === "guardrail_blocked") {
        const gr = String(sig.guardrail ?? "").trim();
        const candidates =
          spansByName.get(gr) ?? spans.filter((s) => s.type === "guardrail");
        for (const sp of candidates) {
          anchorId = String(sp.span_ref ?? "");
          if (anchorId) break;
        }
      } else if (name === "safety_stop" || name === "output_truncated") {
        for (const sp of spans) {
          if (sp.type !== "llm") continue;
          const props =
            sp.properties && typeof sp.properties === "object" ? sp.properties : {};
          const fr = String(sp.finish_reason ?? props.finish_reason ?? "").toLowerCase();
          if (
            name === "safety_stop" &&
            (fr === "safety" || fr === "content_filter" || fr === "content_filtered")
          ) {
            anchorId = String(sp.span_ref ?? "");
            break;
          }
          if (
            name === "output_truncated" &&
            (fr === "length" || fr === "max_tokens" || fr === "max_output_tokens")
          ) {
            anchorId = String(sp.span_ref ?? "");
            break;
          }
        }
      }

      if (!anchorId) {
        anchorKind = "interaction";
        anchorId = interactionRef;
      }
    }

    pending.push(makeSignalHit({ signal: name, kind, anchorKind, anchorId }));
  };

  for (const sig of trigger) append(sig, "trigger");
  for (const sig of context) append(sig, "context");
  return pending;
}
