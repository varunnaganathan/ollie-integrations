# ADK execution model → Ollie warehouse (v0.3.2+)

The integration captures an **internal span tree** from Google ADK hooks, then **normalizes** it to a warehouse-shaped package: one run interaction, `trace_spans`-ready span dicts, and anchored `_signal_hits`.

**Customer API unchanged:** still `attach_ollie(client, app_name=..., flush_mode=...)` once at startup. Both sync `Runner.run` and async `Runner.run_async` are instrumented.

## Capture graph (internal)

| ADK source | Collector node | `ExecutionType` |
|---|---|---|
| `Runner.run` / `run_async` | app root | `workflow` |
| Agent invocation | `agent.name` | `agent` |
| Tool execution | `tool.name` | `tool` |
| LLM generate step | `llm_request.model` | `llm` |

## Wire package (normalized)

Each runner invocation produces **one** `run` interaction:

- **input / output** — user message in, final answer out
- **events.spans** — warehouse-shaped spans (see below); `events.trigger` / `events.context` are empty
- **`_signal_hits`** — anchored instrumented signals (`signal`, `kind`, `anchor_kind`, `anchor_id`)
- **run attributes** — `tool_calls_count` (int), `tool_call_names` (JSON array string of tool span names)

### Span shape

Each span keeps validate fields (`type`, `name`, `status`, `span_ref`) and warehouse interiors:

```json
{
  "type": "tool",
  "name": "search_filings",
  "status": "success",
  "span_ref": "n_3",
  "parent_span_ref": "n_2",
  "input": { "text": "{\"query\": \"...\"}" },
  "output": { "text": "{\"snippets\": [...]}" },
  "properties": {
    "kind": "tool",
    "name": "search_filings",
    "status": "success",
    "duration_ms": 120
  }
}
```

LLM spans also carry `prompt_tokens` / `completion_tokens` / `cached_tokens` / `thoughts_tokens`, `finish_reason`, `error_code`, `error_message` (and `llm_error_message` mirror). Agent spans carry `author` and `agent_branch` when present.

When `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`, `input`/`output` are `{}`.

### Signal hits

Negative-only defaults. P1 surface failures use `anchor_kind=span` (owning tool/llm `span_ref`); P2 run/KPI outcomes use `anchor_kind=interaction`.

```json
[
  { "signal": "tool_error", "kind": "context", "anchor_kind": "span", "anchor_id": "n_3" },
  { "signal": "runtime_failure", "kind": "context", "anchor_kind": "interaction", "anchor_id": "ix_0" }
]
```

Ingest writes these to **`signal_hits`** (and rolls trigger hits into `trace_signal_matches`). Do not rely on `content.events.trigger/context` for ADK defaults.

### Detector catalog (partition_role)

| Signal | Surface | Anchor | `partition_role` |
|--------|---------|--------|------------------|
| `tool_error` | tool | failed tool span | `execution` (P1) |
| `unknown_tool` | tool | failed tool span | `execution` (P1) |
| `llm_error` | llm | failed llm span | `execution` (P1) |
| `safety_stop` | llm | llm `finish_reason` safety/filter | `execution` (P1) |
| `output_truncated` | llm | llm `finish_reason` length/max_tokens | `execution` (P1) |
| `malformed_tool_call` | llm | llm `finish_reason` malformed function call | `execution` (P1) |
| `rate_limited` | llm | llm `error_code` rate-limit | `execution` (P1) |
| `provider_unavailable` | llm | llm `error_code` unavailable/deadline | `execution` (P1) |
| `repeated_tool_error` | tool (pattern, trigger) | first failed tool span | `execution` (P1) |
| `tool_loop` | tool (pattern) | last tool span | `execution` (P1) |
| `runtime_failure` | run | interaction | `outcome` (P2) |
| `empty_final_response` | run | interaction | `outcome` (P2) |
| `high_latency` | run KPI | interaction | `outcome` (P2) |

Dropped neutrals: `used_tool`, `delegation`, `planner_uncertainty`, `input_truncated`. Wire I/O truncation is not a product signal.

## Migration from v0.2.x / v0.3.0

v0.3.0 was a **breaking wire interior** change (same attach API). v0.3.1 added token splits, llm error messages, agent/run metadata, and sync `Runner.run`. v0.3.2 forwards ADK 2.6+ telemetry kwargs (`invocation_context` on tool hooks).

- Query instrumented defaults via `signal_hits`, not `content.events[].name`
- Span metrics and I/O live on `trace_spans` (`input`/`output`/`properties`)

Install: `@google-adk-v0.3.2`

## Phase 2 (future — not in this release)

Same boundary-preserve / interior-reshape pattern, after ADK validates in production:

1. **Agent frameworks:** openai-agents (Py+TS), claude-agent-sdk (Py+TS), crewai, vercel-ai-sdk-ts — warehouse span dicts + `_signal_hits`; customer `attach_*` APIs frozen.
2. **ollie-sdk / `@ollie/sdk` provider tracing:** OpenAI, Anthropic, Gemini instrumentors — generation/tool spans and default signals land in `trace_spans` + `signal_hits`.
3. Shared hit helpers + sdk_ingest persistence (from Phase 1) reused by each package.
4. Coordinated breaking tags (`openai-agents-v0.2.0`, …, sdk bump).
