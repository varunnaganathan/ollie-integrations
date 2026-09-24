# Ollie Langfuse importer

Standalone customer-side importer for Langfuse snapshots. It reads at most
1,000 newest unique records, redacts PII and secrets locally, and uploads
deterministic gzip NDJSON chunks to Ollie. It has no runtime dependencies
outside the Python standard library.

## Install

Python 3.10 or newer is required.

```bash
python -m pip install \
  "ollie-integrations-langfuse @ git+https://github.com/varunnaganathan/ollie-integrations.git@langfuse-v0.1.0#subdirectory=langfuse"
```

Set Ollie credentials in the shell running the importer:

```bash
export OLLIE_API_KEY="..."
export OLLIE_BASE_URL="https://olliemainapi.onrender.com"
```

Credentials are read from environment variables and are never included in
console output, request bodies, checksums, or uploaded trace data.

## Import an exported snapshot

JSON arrays, JSON objects, and newline-delimited JSON (`.jsonl` or `.ndjson`)
are accepted. Wrapped arrays under `data`, `traces`, `observations`, `events`,
or `records` are also accepted.

```bash
ollie-langfuse-import ./langfuse-export.json --limit 1000
ollie-langfuse-import ./langfuse-export.ndjson --limit 500
```

`--limit` must be 1–1,000. Duplicate IDs are collapsed to their newest record,
then records are ordered newest-first with deterministic tie-breaking.

## Fetch from Langfuse locally

The importer calls Langfuse's public traces API from your machine. Langfuse
credentials are not sent to Ollie.

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="https://cloud.langfuse.com"

ollie-langfuse-import --from-langfuse --limit 1000
```

`LANGFUSE_BASE_URL` defaults to `https://cloud.langfuse.com`.

## Privacy and resumability

Before any network request to Ollie, every nested string is scanned for email
addresses, phone numbers, SSNs, IPv4 addresses, payment-card numbers, bearer
tokens, common API-key forms, and AWS access keys. Values under credential-like
keys are always replaced. Repeated sensitive values receive the same
non-reversible pseudonym within an import.

The importer sends deterministic gzip NDJSON chunks with SHA-256 checksums:

- `POST /v1/imports/langfuse` creates or resumes an import.
- `GET /v1/imports/{id}` discovers already accepted chunks.
- `PUT /v1/imports/{id}/chunks/{index}` uploads missing chunks.
- `POST /v1/imports/{id}/complete` verifies and completes the import.

Every mutating request has a content-derived idempotency key. Re-running an
unchanged snapshot is safe. Use `--chunk-records` only when support asks you
to change the default of 100 records per chunk.
