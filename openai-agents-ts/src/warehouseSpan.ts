import type { SpanRecord } from "./types.js";

const PROP_KEYS = [
  "duration_ms",
  "token_count",
  "finish_reason",
  "error_type",
  "triggered",
  "from_agent",
  "to_agent",
] as const;

export function warehouseShapeSpan(span: SpanRecord): SpanRecord {
  const out: SpanRecord = { ...span };
  const spanType = String(out.type ?? "").trim() || "unknown";
  const name = String(out.name ?? "").trim() || spanType;
  const status = String(out.status ?? "success").trim() || "success";

  const props: Record<string, unknown> =
    out.properties && typeof out.properties === "object" ? { ...out.properties } : {};
  if (props.kind === undefined) props.kind = spanType;
  if (props.name === undefined) props.name = name;
  if (props.status === undefined) props.status = status;
  for (const key of PROP_KEYS) {
    if (out[key] !== undefined && props[key] === undefined) props[key] = out[key];
  }
  out.properties = props;

  if (!out.input || typeof out.input !== "object") out.input = {};
  if (!out.output || typeof out.output !== "object") out.output = {};
  return out;
}

export function warehouseShapeSpans(spans: SpanRecord[]): SpanRecord[] {
  return spans.map(warehouseShapeSpan);
}
