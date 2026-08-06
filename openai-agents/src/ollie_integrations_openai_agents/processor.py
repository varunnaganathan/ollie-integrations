"""Map OpenAI Agents TracingProcessor spans to Ollie span records."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from ollie_integrations_openai_agents.collector import RunCollector

class OllieTracingProcessor:
    """TracingProcessor that appends spans to the active RunCollector."""

    def __init__(self) -> None:
        self._open_mono: dict[str, float] = {}

    def on_trace_start(self, trace: Any) -> None:
        _ = trace

    def on_trace_end(self, trace: Any) -> None:
        _ = trace

    def on_span_start(self, span: Any) -> None:
        sid = getattr(span, "span_id", None) or id(span)
        self._open_mono[str(sid)] = time.monotonic()

    def on_span_end(self, span: Any) -> None:
        collector = RunCollector.current()
        if collector is None:
            return
        mapped = _map_span(span, self._open_mono)
        if mapped is not None:
            collector.add_span(mapped)

    def shutdown(self) -> None:
        self._open_mono.clear()

    def force_flush(self) -> None:
        pass


def _parse_iso_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_ms(span: Any, sid: str, open_mono: dict[str, float]) -> int:
    started_at = _parse_iso_ms(getattr(span, "started_at", None))
    ended_at = _parse_iso_ms(getattr(span, "ended_at", None))
    if started_at is not None and ended_at is not None:
        return max(0, int((ended_at - started_at).total_seconds() * 1000))
    started = open_mono.pop(sid, time.monotonic())
    return max(0, int((time.monotonic() - started) * 1000))


def _attach_span_times(entry: dict[str, Any], span: Any) -> None:
    started_at = getattr(span, "started_at", None)
    ended_at = getattr(span, "ended_at", None)
    if started_at:
        entry["started_at"] = str(started_at)
    if ended_at:
        entry["ended_at"] = str(ended_at)


def _token_count_from_usage(usage: Any) -> int | None:
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens") or usage.get("total")
    if total is not None:
        return int(total)
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    if inp is not None or out is not None:
        return int(inp or 0) + int(out or 0)
    return None


def _finish_reason_from_response(data: Any) -> str | None:
    response = getattr(data, "response", None)
    if response is None:
        return None
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete is not None:
        reason = getattr(incomplete, "reason", None)
        if reason:
            return str(reason)
    status = getattr(response, "status", None)
    if status == "completed":
        return "stop"
    if status == "incomplete":
        return "incomplete"
    return None


def _attach_span_identity(entry: dict[str, Any], span: Any) -> None:
    span_ref = getattr(span, "span_id", None)
    if span_ref:
        entry["span_ref"] = str(span_ref)
    parent_id = getattr(span, "parent_id", None)
    if parent_id:
        entry["parent_span_ref"] = str(parent_id)


def _io_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return {"text": str(value)}


def _finalize_span(
    entry: dict[str, Any],
    span: Any,
    *,
    capture_io: bool = True,
) -> dict[str, Any]:
    from ollie_integrations_openai_agents.warehouse_span import warehouse_shape_span

    _attach_span_identity(entry, span)
    _attach_span_times(entry, span)
    if not capture_io:
        entry.setdefault("input", {})
        entry.setdefault("output", {})
        return warehouse_shape_span(entry)

    data = getattr(span, "span_data", None)
    if data is not None and "input" not in entry:
        inp = getattr(data, "input", None) or getattr(data, "arguments", None)
        if inp is not None:
            entry["input"] = _io_dict(inp)
    if data is not None and "output" not in entry:
        out = getattr(data, "output", None) or getattr(data, "result", None)
        if out is not None:
            entry["output"] = _io_dict(out)
    return warehouse_shape_span(entry)


def _map_span(span: Any, open_mono: dict[str, float]) -> dict[str, Any] | None:
    data = getattr(span, "span_data", None)
    if data is None:
        return None
    sdk_type = getattr(data, "type", None) or ""
    sid = str(getattr(span, "span_id", id(span)))
    duration_ms = _duration_ms(span, sid, open_mono)
    error = getattr(span, "error", None)
    status = "failure" if error else "success"

    if sdk_type == "function":
        name = getattr(data, "name", None) or "function"
        entry: dict[str, Any] = {
            "type": "tool",
            "name": str(name),
            "status": status,
            "duration_ms": duration_ms,
        }
        if error:
            entry["error_type"] = str(error.get("message") if isinstance(error, dict) else error)
        return _finalize_span(entry, span)

    if sdk_type == "generation":
        model = getattr(data, "model", None) or "llm"
        entry = {"type": "llm", "name": str(model), "status": status, "duration_ms": duration_ms}
        token_count = _token_count_from_usage(getattr(data, "usage", None))
        if token_count is not None:
            entry["token_count"] = token_count
        return _finalize_span(entry, span)

    if sdk_type == "response":
        response = getattr(data, "response", None)
        model = getattr(response, "model", None) if response is not None else None
        entry = {
            "type": "llm",
            "name": str(model or "response"),
            "status": status,
            "duration_ms": duration_ms,
        }
        token_count = _token_count_from_usage(getattr(data, "usage", None))
        if token_count is not None:
            entry["token_count"] = token_count
        finish_reason = _finish_reason_from_response(data)
        if finish_reason:
            entry["finish_reason"] = finish_reason
        return _finalize_span(entry, span)

    if sdk_type == "handoff":
        fa = getattr(data, "from_agent", None) or "?"
        ta = getattr(data, "to_agent", None) or "?"
        return _finalize_span(
            {
                "type": "handoff",
                "name": f"{fa} → {ta}",
                "status": status,
                "duration_ms": duration_ms,
                "from_agent": fa,
                "to_agent": ta,
            },
            span,
            capture_io=False,
        )

    if sdk_type == "agent":
        return _finalize_span(
            {
                "type": "agent",
                "name": str(getattr(data, "name", None) or "agent"),
                "status": status,
                "duration_ms": duration_ms,
            },
            span,
            capture_io=False,
        )

    if sdk_type == "guardrail":
        triggered = bool(getattr(data, "triggered", False))
        st = "failure" if triggered or status == "failure" else "success"
        return _finalize_span(
            {
                "type": "guardrail",
                "name": str(getattr(data, "name", None) or "guardrail"),
                "status": st,
                "duration_ms": duration_ms,
                "triggered": triggered,
            },
            span,
            capture_io=False,
        )

    if sdk_type == "custom":
        name = getattr(data, "name", None) or "custom"
        entry = {
            "type": "custom",
            "name": str(name),
            "status": status,
            "duration_ms": duration_ms,
        }
        # Prefer explicit input/output; else optional data dict as input metadata.
        custom_data = getattr(data, "data", None)
        if getattr(data, "input", None) is not None:
            entry["input"] = _io_dict(getattr(data, "input"))
        elif isinstance(custom_data, dict) and custom_data:
            entry["input"] = dict(custom_data)
        if getattr(data, "output", None) is not None:
            entry["output"] = _io_dict(getattr(data, "output"))
        return _finalize_span(entry, span, capture_io=False)

    if sdk_type in ("turn", "task"):
        return None

    return None


def register_processor() -> OllieTracingProcessor:
    from agents.tracing import add_trace_processor

    processor = OllieTracingProcessor()
    add_trace_processor(processor)
    return processor
