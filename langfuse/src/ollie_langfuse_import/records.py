"""Load and deterministically select records from Langfuse snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MAX_RECORDS = 1000
MAX_OBSERVATIONS_PER_TRACE = 5_000
_ID_FIELDS = ("id", "traceId", "trace_id", "eventId", "event_id")
_TIME_FIELDS = (
    "timestamp",
    "startTime",
    "start_time",
    "createdAt",
    "created_at",
    "updatedAt",
    "updated_at",
)


class InputError(ValueError):
    """The local snapshot cannot be read as supported JSON."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _records_from_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, dict):
        candidates = next(
            (
                value[key]
                for key in ("data", "traces", "observations", "events", "records")
                if isinstance(value.get(key), list)
            ),
            [value],
        )
    else:
        raise InputError("JSON input must be an object, array, or NDJSON objects")
    return [item for item in candidates if isinstance(item, dict)]


def load_dump(path: str | Path) -> list[dict[str, Any]]:
    """Read JSON, JSONL, or NDJSON. Invalid NDJSON lines fail closed."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise InputError(f"cannot read snapshot: {exc}") from exc
    if not text.strip():
        raise InputError("snapshot is empty")

    try:
        return _records_from_json(json.loads(text))
    except json.JSONDecodeError:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InputError(f"invalid NDJSON on line {line_number}") from exc
            if not isinstance(value, dict):
                raise InputError(f"NDJSON line {line_number} is not an object")
            records.append(value)
        if not records:
            raise InputError("snapshot contains no records")
        return records


def _identity(record: dict[str, Any]) -> str:
    for field in _ID_FIELDS:
        value = record.get(field)
        if value is not None and str(value):
            return f"{field}:{value}"
    return "sha256:" + hashlib.sha256(canonical_json(record)).hexdigest()


def _timestamp(record: dict[str, Any]) -> float:
    for field in _TIME_FIELDS:
        value = record.get(field)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp()
            except ValueError:
                continue
    return float("-inf")


def _trim_observations(record: dict[str, Any]) -> dict[str, Any]:
    """Keep at most MAX_OBSERVATIONS_PER_TRACE observations in-place on a copy."""
    out = dict(record)
    observations = out.get("observations")
    if isinstance(observations, list) and len(observations) > MAX_OBSERVATIONS_PER_TRACE:
        out["observations"] = observations[:MAX_OBSERVATIONS_PER_TRACE]
        meta = dict(out.get("_ollie_trim") or {})
        meta["observations_truncated"] = len(observations) - MAX_OBSERVATIONS_PER_TRACE
        out["_ollie_trim"] = meta
    elif isinstance(out.get("data"), dict):
        data = dict(out["data"])
        nested = data.get("observations")
        if isinstance(nested, list) and len(nested) > MAX_OBSERVATIONS_PER_TRACE:
            data["observations"] = nested[:MAX_OBSERVATIONS_PER_TRACE]
            out["data"] = data
            meta = dict(out.get("_ollie_trim") or {})
            meta["observations_truncated"] = len(nested) - MAX_OBSERVATIONS_PER_TRACE
            out["_ollie_trim"] = meta
    return out


def select_records(
    records: Iterable[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Keep the newest version of each identity, then the newest N records."""
    if not 1 <= limit <= MAX_RECORDS:
        raise ValueError(f"limit must be between 1 and {MAX_RECORDS}")

    unique: dict[str, tuple[tuple[float, bytes], dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        record = _trim_observations(record)
        key = _identity(record)
        rank = (_timestamp(record), canonical_json(record))
        if key not in unique or rank > unique[key][0]:
            unique[key] = (rank, record)

    ordered = sorted(
        unique.items(),
        key=lambda item: (item[1][0][0], item[0], item[1][0][1]),
        reverse=True,
    )
    return [entry[1][1] for entry in ordered[:limit]]
