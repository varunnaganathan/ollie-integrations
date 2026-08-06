"""In-memory collector for one OpenAI Agents run()."""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_current_collector: ContextVar[RunCollector | None] = ContextVar("ollie_openai_run_collector", default=None)

# Structural / built-in keys that custom span attrs must not overwrite.
_RESERVED_PROP_KEYS = frozenset(
    {
        "kind",
        "name",
        "status",
        "duration_ms",
        "token_count",
        "finish_reason",
        "error_type",
        "triggered",
        "from_agent",
        "to_agent",
    }
)


@dataclass
class RunCollector:
    """One workflow invocation: run input/output + flat execution spans."""

    workflow_name: str
    session_id: str | None = None
    input_text: str = ""
    output_text: str = ""
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: str | None = None
    status: str = "completed"
    spans: list[dict[str, Any]] = field(default_factory=list)
    run_attributes: dict[str, Any] = field(default_factory=dict)
    user_signal_hits: list[dict[str, Any]] = field(default_factory=list)
    _open_span_stack: list[str] = field(default_factory=list)
    _pending_span_attrs: dict[str, dict[str, Any]] = field(default_factory=dict)
    _started_mono: float = field(default_factory=time.monotonic)

    @classmethod
    def current(cls) -> RunCollector | None:
        return _current_collector.get()

    @classmethod
    def set_current(cls, collector: RunCollector | None) -> None:
        _current_collector.set(collector)

    def close(self, *, output: str = "", success: bool = True) -> None:
        self.output_text = output
        self.status = "completed" if success else "failed"
        self.ended_at = utc_now_iso()

    @property
    def latency_ms(self) -> int:
        return int((time.monotonic() - self._started_mono) * 1000)

    def push_open_span(self, span_id: str) -> None:
        sid = str(span_id or "").strip()
        if sid:
            self._open_span_stack.append(sid)

    def pop_open_span(self, span_id: str) -> None:
        sid = str(span_id or "").strip()
        if not sid:
            return
        if self._open_span_stack and self._open_span_stack[-1] == sid:
            self._open_span_stack.pop()
            return
        if sid in self._open_span_stack:
            self._open_span_stack = [x for x in self._open_span_stack if x != sid]

    def current_span_id(self) -> str | None:
        return self._open_span_stack[-1] if self._open_span_stack else None

    def merge_run_attributes(self, attributes: dict[str, Any]) -> None:
        for name, value in attributes.items():
            key = str(name or "").strip()
            if key:
                self.run_attributes[key] = value

    def merge_pending_span_attributes(self, attributes: dict[str, Any]) -> None:
        sid = self.current_span_id()
        if not sid or not attributes:
            return
        bucket = self._pending_span_attrs.setdefault(sid, {})
        for name, value in attributes.items():
            key = str(name or "").strip()
            if key:
                bucket[key] = value

    def append_signal_hit(
        self,
        name: str,
        *,
        kind: str = "context",
        span_ref: str | None = None,
    ) -> None:
        sig = str(name or "").strip()
        if not sig:
            return
        k = str(kind or "context").strip()
        if k not in ("context", "trigger"):
            k = "context"
        sid = (span_ref or self.current_span_id() or "").strip()
        if sid:
            hit = {
                "signal": sig,
                "kind": k,
                "anchor_kind": "span",
                "anchor_id": sid,
            }
        else:
            hit = {
                "signal": sig,
                "kind": k,
                "anchor_kind": "interaction",
                "anchor_id": "ix_0",
            }
        self.user_signal_hits.append(hit)

    def add_span(self, span: dict[str, Any]) -> None:
        out = dict(span)
        sid = str(out.get("span_ref") or "").strip()
        pending = self._pending_span_attrs.pop(sid, None) if sid else None
        if pending:
            props = dict(out.get("properties") or {}) if isinstance(out.get("properties"), dict) else {}
            for key, value in pending.items():
                if key in _RESERVED_PROP_KEYS or key in props:
                    continue
                props[key] = value
            out["properties"] = props
        self.spans.append(out)
