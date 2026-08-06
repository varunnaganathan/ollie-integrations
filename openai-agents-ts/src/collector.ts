import { AsyncLocalStorage } from "node:async_hooks";

import type { SpanRecord } from "./types.js";

const RESERVED_PROP_KEYS = new Set([
  "kind",
  "name",
  "status",
  "duration_ms",
  "token_count",
  "finish_reason",
  "error_type",
  "triggered",
  "from_agent",
  "to_agent",
]);

type SignalHit = {
  signal: string;
  kind: string;
  anchor_kind: "span" | "interaction";
  anchor_id: string;
};

const currentCollector = new AsyncLocalStorage<RunCollector | null>();

export class RunCollector {
  workflowName: string;
  sessionId?: string;
  inputText = "";
  outputText = "";
  startedAt: string;
  endedAt?: string;
  status: "completed" | "failed" = "completed";
  spans: SpanRecord[] = [];
  runAttributes: Record<string, unknown> = {};
  userSignalHits: SignalHit[] = [];
  private openSpanStack: string[] = [];
  private pendingSpanAttrs: Record<string, Record<string, unknown>> = {};
  private startedMono = Date.now();

  constructor(opts: { workflowName: string; sessionId?: string; inputText?: string }) {
    this.workflowName = opts.workflowName;
    this.sessionId = opts.sessionId;
    this.inputText = opts.inputText ?? "";
    this.startedAt = new Date().toISOString();
  }

  static current(): RunCollector | null {
    return currentCollector.getStore() ?? null;
  }

  static runWith<T>(collector: RunCollector, fn: () => T): T {
    return currentCollector.run(collector, fn);
  }

  static enterWith(collector: RunCollector | null): void {
    currentCollector.enterWith(collector);
  }

  close(output: string, success: boolean): void {
    this.outputText = output;
    this.status = success ? "completed" : "failed";
    this.endedAt = new Date().toISOString();
  }

  get latencyMs(): number {
    return Date.now() - this.startedMono;
  }

  pushOpenSpan(spanId: string): void {
    const sid = String(spanId ?? "").trim();
    if (sid) this.openSpanStack.push(sid);
  }

  popOpenSpan(spanId: string): void {
    const sid = String(spanId ?? "").trim();
    if (!sid) return;
    if (this.openSpanStack.at(-1) === sid) {
      this.openSpanStack.pop();
      return;
    }
    this.openSpanStack = this.openSpanStack.filter((x) => x !== sid);
  }

  currentSpanId(): string | null {
    return this.openSpanStack.at(-1) ?? null;
  }

  mergeRunAttributes(attributes: Record<string, unknown>): void {
    for (const [name, value] of Object.entries(attributes)) {
      const key = String(name ?? "").trim();
      if (key) this.runAttributes[key] = value;
    }
  }

  mergePendingSpanAttributes(attributes: Record<string, unknown>): void {
    const sid = this.currentSpanId();
    if (!sid) return;
    const bucket = (this.pendingSpanAttrs[sid] ??= {});
    for (const [name, value] of Object.entries(attributes)) {
      const key = String(name ?? "").trim();
      if (key) bucket[key] = value;
    }
  }

  appendSignalHit(
    name: string,
    opts: { kind?: string; spanRef?: string | null } = {},
  ): void {
    const sig = String(name ?? "").trim();
    if (!sig) return;
    let kind = String(opts.kind ?? "context").trim();
    if (kind !== "context" && kind !== "trigger") kind = "context";
    const sid = String(opts.spanRef ?? this.currentSpanId() ?? "").trim();
    this.userSignalHits.push(
      sid
        ? { signal: sig, kind, anchor_kind: "span", anchor_id: sid }
        : { signal: sig, kind, anchor_kind: "interaction", anchor_id: "ix_0" },
    );
  }

  addSpan(span: SpanRecord): void {
    const out: SpanRecord = { ...span, properties: { ...(span.properties ?? {}) } };
    const sid = String(out.span_ref ?? "").trim();
    const pending = sid ? this.pendingSpanAttrs[sid] : undefined;
    if (pending) {
      delete this.pendingSpanAttrs[sid];
      const props = { ...(out.properties ?? {}) };
      for (const [key, value] of Object.entries(pending)) {
        if (RESERVED_PROP_KEYS.has(key) || props[key] != null) continue;
        props[key] = value;
      }
      out.properties = props;
    }
    this.spans.push(out);
  }
}

export function toInputStr(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
