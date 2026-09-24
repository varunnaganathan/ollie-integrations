---
name: ollie-instrument-v3
description: Catalog-driven closed-loop onboarding — fetch pins from the catalog API, instrument from docs_url, poll probe until ok; never ask Ollie support whether traces landed.
---

# Ollie instrumentation (v3 — catalog + probe)

Use when onboarding with Ollie or adding tracing.

This skill **does not embed install pins**. Pins, detect rules, and docs URLs come from the **catalog API**. Adding a new integration is a catalog update only.

**v1** (fat how-tos, unchanged): `skills/ollie-instrument/SKILL.md`
**v2** (router with hardcoded pins, unchanged): `skills/ollie-instrument-v2/SKILL.md`

## Required environment

Do **not** invent credentials. Use onboarding / `.ollie/env.sh` / customer-provided values.

If `OLLIE_API_KEY` or `OLLIE_AGENT_ID` is unset, stop and fix env before calling ingest. Missing env never reaches Ollie (`NEVER_FLUSHED`). HTTP **401** on probe/ingest means `AUTH_MISSING` (bad or missing key).

```bash
export OLLIE_API_KEY="..."
export OLLIE_AGENT_ID="..."
export OLLIE_BASE_URL="${OLLIE_BASE_URL:-https://olliemainapi.onrender.com}"
export OLLIE_INGEST_BASE_URL="${OLLIE_INGEST_BASE_URL:-https://olliejudge-sentry-backend.onrender.com}"
```

(`OLLIE_CLOUD_INGEST_BASE_URL` is an alias for `OLLIE_INGEST_BASE_URL` if set.)

## Langfuse snapshot preflight

Before framework detection, look for a customer-provided Langfuse export:
`*langfuse*.json`, `*langfuse*.jsonl`, or `*langfuse*.ndjson`. Also treat
`LANGFUSE_PUBLIC_KEY` plus `LANGFUSE_SECRET_KEY` as an explicit request to
import directly from Langfuse. Do not print or copy any credential value into
chat, logs, command arguments, or files.

Install the standalone importer exactly:

```bash
python -m pip install \
  "ollie-integrations-langfuse @ git+https://github.com/varunnaganathan/ollie-integrations.git@langfuse-v0.1.0#subdirectory=langfuse"
```

For a detected snapshot, use its real path in this exact command:

```bash
export OLLIE_BASE_URL="${OLLIE_BASE_URL:-https://olliemainapi.onrender.com}"
ollie-langfuse-import "./path/to/langfuse-export.json" --limit 1000
```

For an explicit local Langfuse connection, require
`LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`; `LANGFUSE_BASE_URL` defaults
to Langfuse Cloud:

```bash
export LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-https://cloud.langfuse.com}"
export OLLIE_BASE_URL="${OLLIE_BASE_URL:-https://olliemainapi.onrender.com}"
ollie-langfuse-import --from-langfuse --limit 1000
```

The importer performs mandatory local PII and secret redaction before upload;
the server redacts again before persistence. Never bypass it by uploading a
dump with `curl`. For snapshot-only onboarding, stop after the command returns
the dashboard and report URLs: skip source instrumentation, the local checker,
and trace probe. If the customer also requested continuous live tracing,
continue through the closed loop below as a separate path.

## Closed loop (mandatory)

**Done** only when probe returns `"ok": true` for **this** `test-offline` session. Do not wait for unknown-unknown issues. Do not use tenant-wide diagnose `trace_count` as the stop condition.

Python: create a worktree `.venv` and use **that** interpreter for pip and the sample (`./.venv/bin/python`). Do not mix system `pip` with a different `python3`.

```text
MAX = 4
1. Confirm OLLIE_API_KEY + OLLIE_AGENT_ID in the same env that runs the app
2. GET $OLLIE_INGEST_BASE_URL/v1/sdk/instrumentation/catalog  (no API key)
3. Match this repo to integrations[] using detect.imports / detect.pypi / detect.npm.
   If several match, pick the lowest priority number (frameworks beat generic SDK).
4. Install that entry's install.pip or install.npm exactly. Fetch docs_url and follow it
   for attach stubs. Do not invent APIs from memory. Do not use install lines from this skill.
5. Apply the smallest patch from those docs to the **existing sample entrypoint**
   (`main.py`, `main.ts`, `run.py` — whichever the repo already runs). Wrap the
   real LLM/agent call in `workflow` / `attach_ollie` / `attachOllie`, then call
   `flush_ingest` / `flushIngest` from that same file. Do not only run a one-off
   `python -c` / throwaway script.
6. Choose session_id: must contain "test-offline" and be <= 36 chars
   (example: test-offline-a1b2c3d4). Use it as the trace/session id for the sample run.
   Python OpenAI Agents: export OLLIE_SESSION_ID; do not pass session_id to Runner.run.
7. VALIDATE flush (flush_mode=validate). Inspect the HTTP body — require accepted.
   If accepted false, apply issues[].fix from the validate body when path is set; retry. Do not ingest yet.
8. INGEST flush (flush_mode=ingest) with the same session_id.
9. POLL GET probe at most 3 times, 5 seconds apart. No long sleep loops.
   If HTTP 401 → AUTH_MISSING (fix key). Else apply issues[].fix when issues[].path is set.
10. If the same error_code repeats with empty path, or PERSIST_FAILED says ingest worker
    bug: STOP. Do not invent a new session_id. Cap MAX attempts, then hand off with evidence.
```

Never mark instrumentation done while probe `ok` is false.

If `SCHEMA_REJECTED` / `PERSIST_FAILED` has **no** `issues[].path`, that is a server/worker problem — do not patch the payload.

### Curls

```bash
# Public catalog (no API key)
curl -sS "$OLLIE_INGEST_BASE_URL/v1/sdk/instrumentation/catalog"

# After ingest — poll until ok (same test-offline session_id)
curl -sS -H "X-API-Key: $OLLIE_API_KEY" \
  "$OLLIE_INGEST_BASE_URL/v1/sdk/onboarding/probe?agent_id=$OLLIE_AGENT_ID&session_id=$SESSION_ID"
```

Probe fields: `ok`, `error_code`, `issues[]` (`code`, `path`, `message`, `fix`, `got`, `expected`), `next_action`, `nearby_session_ids`.

**Always apply `issues[].fix` in order.** Do not invent a patch from `error_code` alone.

| error_code | Meaning |
|------------|---------|
| `OK` | Warehouse trace exists for this session — done |
| `MISSING_WORKFLOW` | No workflow object — wrap run / attach_ollie |
| `EMPTY_INTERACTIONS` | Flush before a real run |
| `MISSING_AGENT_ID` | Set `OLLIE_AGENT_ID` |
| `SESSION_ID_TOO_LONG` | session_id > 36 chars — use `test-offline-<8hex>` |
| `SCHEMA_REJECTED` | Field errors — follow `issues[].path` + `fix`. If path is empty, stop (server). |
| `NO_SPANS` | Validate ok but no child spans — fix attach/tracing |
| `VALIDATE_ONLY` | You validated but never ingested |
| `NEVER_FLUSHED` | Nothing reached ingest for this session |
| `SESSION_ID_MISMATCH` | You flushed a different test-offline id — see `nearby_session_ids` |
| `AGENT_ID_MISMATCH` | Wrong `OLLIE_AGENT_ID` |
| `QUEUED` | Re-poll (max 3). Do not change code yet |
| `PERSIST_FAILED` | Warehouse/worker — follow `issues[].fix`. If it says worker bug, stop |
| HTTP 401 | `AUTH_MISSING` — fix `OLLIE_API_KEY` |

HTTP 200 on `/v1/sdk/events/batch` does **not** mean a warehouse trace exists — always confirm with **probe**.

Optional after probe ok: dashboard `https://{slug}.tryollie.com/data`. Unknown-unknown issues are a later product step, not this loop.

## Detect (from catalog only)

Do not hardcode framework names beyond matching catalog `detect` fields against the repo (`pyproject.toml`, `package.json`, imports).
