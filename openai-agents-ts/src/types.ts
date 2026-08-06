export type SpanRecord = {
  type: string;
  name: string;
  status: "success" | "failure";
  span_ref: string;
  parent_span_ref?: string;
  duration_ms?: number;
  token_count?: number;
  finish_reason?: string;
  from_agent?: string;
  to_agent?: string;
  triggered?: boolean;
  error_type?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  properties?: Record<string, unknown>;
};

export type Signal = { name: string; [key: string]: unknown };

export type SignalHit = {
  signal: string;
  kind: string;
  anchor_kind: "span" | "interaction";
  anchor_id: string;
};

export type EventsDict = {
  trigger: Signal[];
  context: Signal[];
  spans: SpanRecord[];
};

export type RunInteraction = {
  interaction_ref: string;
  parent_interaction_ref: null;
  interaction_type: "run";
  name: string;
  input: string;
  output: string;
  events: EventsDict;
  _signal_hits: SignalHit[];
  attributes: Array<{ name: string; value: unknown }>;
  started_at: string;
  ended_at: string;
};

export type WirePayload = {
  schema_version: 2;
  sdk: { name: string; version: string };
  agent_id: string;
  session_id: string;
  workflow: {
    name: string;
    status: string;
    started_at: string;
    ended_at: string;
  };
  interactions: RunInteraction[];
};

export type OllieClient = {
  agent_id: string;
  _transport: {
    validate_trace: (p: WirePayload, d: unknown) => Promise<unknown>;
    process_trace: (p: WirePayload, d: unknown) => Promise<unknown>;
    ingest_trace: (p: WirePayload, d: unknown) => Promise<unknown>;
  };
  _delivery: unknown;
};
