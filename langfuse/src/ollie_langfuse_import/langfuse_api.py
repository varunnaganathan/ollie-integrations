"""Small Langfuse public API client using only the Python standard library."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

MAX_OBSERVATIONS_PER_TRACE = 5_000
MAX_FIELD_CHARS = 100_000


class LangfuseError(RuntimeError):
    pass


class _Client:
    def __init__(self, public_key: str, secret_key: str, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    def get(self, path: str, attempts: int = 3) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            headers={
                "Authorization": f"Basic {self.auth}",
                "Accept": "application/json",
                "User-Agent": "ollie-langfuse-import/0.1",
            },
        )
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise LangfuseError("Langfuse returned an unexpected response")
                return payload
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                if attempt + 1 >= attempts:
                    raise LangfuseError("Langfuse trace retrieval failed") from exc
                time.sleep(0.25 * (2**attempt))
        raise LangfuseError("Langfuse trace retrieval failed")


def _cap(value: Any, depth: int = 0) -> Any:
    if depth > 30:
        return "<OLLIE_TRUNCATED_DEPTH>"
    if isinstance(value, str):
        return value[:MAX_FIELD_CHARS]
    if isinstance(value, list):
        return [_cap(item, depth + 1) for item in value]
    if isinstance(value, dict):
        return {str(key): _cap(item, depth + 1) for key, item in value.items()}
    return value


def _observations(client: _Client, trace_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"traceId": trace_id, "page": page, "limit": 100}
        )
        payload = client.get(f"/api/public/observations?{query}")
        data = payload.get("data")
        if not isinstance(data, list):
            raise LangfuseError("Langfuse observations returned an unexpected response")
        for item in data:
            if isinstance(item, dict):
                rows.append(_cap(item))
            if len(rows) >= MAX_OBSERVATIONS_PER_TRACE:
                return rows
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        total_pages = meta.get("totalPages")
        if (isinstance(total_pages, int) and page >= total_pages) or len(data) < 100:
            break
        page += 1
    return rows


def _record(client: _Client, trace: dict[str, Any]) -> dict[str, Any]:
    trace_id = str(trace.get("id") or "").strip()
    if not trace_id:
        raise LangfuseError("Langfuse trace is missing an id")
    trace_input = trace.get("input") if isinstance(trace.get("input"), dict) else {}
    observations = trace.get("observations")
    if not isinstance(observations, list):
        observations = _observations(client, trace_id)
    else:
        observations = [_cap(item) for item in observations if isinstance(item, dict)]
        if len(observations) > MAX_OBSERVATIONS_PER_TRACE:
            observations = observations[:MAX_OBSERVATIONS_PER_TRACE]
    return {
        "trace_id": trace_id,
        "timestamp": trace.get("timestamp") or trace.get("createdAt"),
        "project_id": trace.get("projectId") or trace.get("name"),
        "session_id": trace.get("sessionId"),
        "user_id": trace.get("userId") or trace_input.get("user_id"),
        "message": trace_input.get("message") or trace.get("input"),
        "input": _cap(trace.get("input")),
        "output": _cap(trace.get("output")),
        "trace_list": _cap(trace),
        "observations": observations,
    }


def fetch_traces(
    public_key: str, secret_key: str, base_url: str, limit: int
) -> list[dict[str, Any]]:
    if not public_key or not secret_key:
        raise LangfuseError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required"
        )
    if not base_url.lower().startswith(("https://", "http://")):
        raise LangfuseError("LANGFUSE_BASE_URL must be an http(s) URL")

    client = _Client(public_key, secret_key, base_url)
    traces: list[dict[str, Any]] = []
    page = 1
    while len(traces) < limit:
        page_limit = min(100, limit - len(traces))
        query = urllib.parse.urlencode(
            {
                "page": page,
                "limit": page_limit,
                "orderBy": "timestamp.desc",
            }
        )
        payload = client.get(f"/api/public/traces?{query}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise LangfuseError("Langfuse returned an unexpected response")
        batch = [item for item in data if isinstance(item, dict)]
        traces.extend(batch)
        total_pages = (
            payload.get("meta", {}).get("totalPages")
            if isinstance(payload.get("meta"), dict)
            else None
        )
        if isinstance(total_pages, int) and page >= total_pages:
            break
        if not isinstance(total_pages, int) and len(data) < page_limit:
            break
        page += 1

    records: list[dict[str, Any] | None] = [None] * len(traces)
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(traces)))) as pool:
        futures = {
            pool.submit(_record, client, trace): index
            for index, trace in enumerate(traces)
        }
        for future in as_completed(futures):
            records[futures[future]] = future.result()
    return [record for record in records if record is not None]
