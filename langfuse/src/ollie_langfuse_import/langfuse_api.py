"""Small Langfuse public API client using only the Python standard library."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
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
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise LangfuseError("Langfuse returned an unexpected response")
                return payload
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                # New orgs (2026-09-16+) reject legacy list APIs with 410.
                if exc.code == 410:
                    raise LangfuseError(f"LEGACY_API_UNAVAILABLE:{detail[:500]}") from exc
                if attempt + 1 >= attempts or exc.code in {401, 403, 404}:
                    raise LangfuseError(
                        f"Langfuse request failed HTTP {exc.code}: {detail[:500]}"
                    ) from exc
                time.sleep(0.25 * (2**attempt))
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


def _fetch_traces_legacy(client: _Client, limit: int) -> list[dict[str, Any]]:
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


def _attr_map(observation: dict[str, Any]) -> dict[str, Any]:
    meta = observation.get("metadata")
    if isinstance(meta, dict):
        return meta
    return {}


def _fetch_traces_v2(client: _Client, limit: int) -> list[dict[str, Any]]:
    """Rebuild traces from GET /api/public/v2/observations for new Langfuse orgs."""
    end = datetime.now(timezone.utc) + timedelta(hours=1)
    start = end - timedelta(days=30)
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cursor: str | None = None
    pages = 0
    while pages < 100 and len(by_trace) < max(limit * 3, limit):
        pages += 1
        params: dict[str, str] = {
            "fromStartTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "toStartTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": "100",
        }
        if cursor:
            params["cursor"] = cursor
        payload = client.get(
            "/api/public/v2/observations?" + urllib.parse.urlencode(params)
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise LangfuseError("Langfuse v2 observations returned an unexpected response")
        for item in data:
            if not isinstance(item, dict):
                continue
            trace_id = str(item.get("traceId") or "").strip()
            if not trace_id:
                continue
            by_trace[trace_id].append(_cap(item))
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        cursor = meta.get("cursor") if isinstance(meta.get("cursor"), str) else None
        if not cursor or not data:
            break

    ranked = sorted(
        by_trace.items(),
        key=lambda pair: max(
            (str(obs.get("startTime") or "") for obs in pair[1]),
            default="",
        ),
        reverse=True,
    )[:limit]

    records: list[dict[str, Any]] = []
    for trace_id, observations in ranked:
        observations = sorted(
            observations,
            key=lambda obs: str(obs.get("startTime") or ""),
        )[:MAX_OBSERVATIONS_PER_TRACE]
        root = observations[0] if observations else {}
        candidates = sorted(
            observations,
            key=lambda obs: (
                1 if obs.get("parentObservationId") else 0,
                str(obs.get("startTime") or ""),
            ),
        )
        envelope = candidates[0] if candidates else root
        env_meta = _attr_map(envelope)
        timestamp = envelope.get("startTime") or root.get("startTime")
        trace = {
            "id": trace_id,
            "timestamp": timestamp,
            "createdAt": timestamp,
            "name": envelope.get("name") or "imported-trace",
            "sessionId": env_meta.get("session.id") or env_meta.get("sessionId"),
            "userId": env_meta.get("user.id") or env_meta.get("userId"),
            "input": env_meta.get("langfuse.trace.input") or envelope.get("input"),
            "output": env_meta.get("langfuse.trace.output") or envelope.get("output"),
            "metadata": {
                "import_source": "langfuse_v2_observations",
                **{k: v for k, v in env_meta.items() if str(k).startswith("ollie.")},
            },
            "observations": observations,
        }
        records.append(_record(client, trace))
    return records


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
    try:
        return _fetch_traces_legacy(client, limit)
    except LangfuseError as exc:
        if "LEGACY_API_UNAVAILABLE" not in str(exc):
            raise
        return _fetch_traces_v2(client, limit)
