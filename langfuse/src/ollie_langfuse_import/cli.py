"""Command-line entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Sequence

from .langfuse_api import LangfuseError, fetch_traces
from .records import MAX_RECORDS, InputError, canonical_json, load_dump, select_records
from .redact import Redactor
from .upload import OllieImportClient, UploadError, make_chunks


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="ollie-langfuse-import",
        description="Redact and import a Langfuse trace snapshot into Ollie.",
    )
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "snapshot",
        nargs="?",
        help="Langfuse JSON, JSONL, or NDJSON dump",
    )
    source.add_argument(
        "--from-langfuse",
        action="store_true",
        help="fetch traces with local LANGFUSE_* credentials",
    )
    result.add_argument(
        "--limit",
        type=int,
        default=MAX_RECORDS,
        help=f"newest unique records to import (1-{MAX_RECORDS})",
    )
    result.add_argument(
        "--chunk-records",
        type=int,
        default=100,
        help="records per gzip NDJSON chunk (default: 100)",
    )
    result.add_argument(
        "--no-wait",
        action="store_true",
        help="return after queueing instead of polling analysis progress",
    )
    return result


def run(argv: Sequence[str] | None = None) -> dict:
    args = parser().parse_args(argv)
    if not 1 <= args.limit <= MAX_RECORDS:
        raise InputError(f"--limit must be between 1 and {MAX_RECORDS}")
    if args.chunk_records < 1:
        raise InputError("--chunk-records must be positive")

    if args.from_langfuse:
        records = fetch_traces(
            os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            os.environ.get("LANGFUSE_SECRET_KEY", ""),
            os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
            MAX_RECORDS,
        )
    else:
        records = load_dump(args.snapshot)

    selected = select_records(records, args.limit)
    if not selected:
        raise InputError("snapshot contains no accepted object records")

    fingerprint = hashlib.sha256(canonical_json(selected)).digest()
    redactor = Redactor(fingerprint)
    redacted = [redactor.value(record) for record in selected]
    chunks = make_chunks(redacted, args.chunk_records)

    client = OllieImportClient(
        os.environ.get("OLLIE_API_KEY", ""),
        os.environ.get("OLLIE_BASE_URL", ""),
    )
    result = client.upload(chunks, len(redacted))
    import_id = result.get("id", result.get("import_id"))
    status = str(result.get("status") or "").lower()
    if (
        not args.no_wait
        and isinstance(import_id, str)
        and status not in {"completed", "complete", "partial", "failed", "cancelled"}
    ):
        result = client.poll(import_id)
    if isinstance(import_id, str):
        dashboard_base = os.environ.get("OLLIE_DASHBOARD_URL", "").rstrip("/")
        result.setdefault(
            "dashboard_url",
            f"{dashboard_base}/imports/{import_id}" if dashboard_base else f"/imports/{import_id}",
        )
        result.setdefault(
            "report_url",
            f"{os.environ.get('OLLIE_BASE_URL', '').rstrip('/')}/v1/imports/{import_id}/report",
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (InputError, LangfuseError, UploadError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    safe_result = {
        key: value
        for key, value in result.items()
        if key
        in {
            "id",
            "import_id",
            "status",
            "record_count",
            "accepted",
            "dashboard_url",
            "report_url",
        }
    }
    print(json.dumps(safe_result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
