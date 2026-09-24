# Langfuse snapshot analysis

This is a one-time, local export—not a persistent Langfuse connector. Langfuse
credentials stay on your machine. Ollie analyzes at most 1,000 newest unique
traces and creates draft results; it does not activate production monitors.

## Install

```bash
python -m pip install "ollie-integrations-langfuse @ git+https://github.com/varunnaganathan/ollie-integrations.git@langfuse-v0.1.0#subdirectory=langfuse"
```

Set `OLLIE_API_KEY` and `OLLIE_BASE_URL`. Set `OLLIE_DASHBOARD_URL` if you want
the command to print an absolute dashboard URL.

## Analyze a dump

```bash
ollie-langfuse-import ./langfuse-export.json
```

JSON, JSONL, and NDJSON dumps are supported.

## Export locally from Langfuse and analyze

Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally
`LANGFUSE_BASE_URL`, then run:

```bash
ollie-langfuse-import --from-langfuse
```

The CLI reads Langfuse credentials only from the local environment. It
deduplicates and selects traces deterministically, redacts PII and secrets
before upload, uploads resumable gzip-NDJSON chunks, and polls the durable
analysis progress. Ollie applies mandatory server-side redaction again before
storing canonical traces.

The final dashboard and downloadable report include capability findings,
definitions of good, draft judges and eval specs, turn-level and trace-level
unknown-unknowns, datasets, improvements, and a path to continuous coverage.
