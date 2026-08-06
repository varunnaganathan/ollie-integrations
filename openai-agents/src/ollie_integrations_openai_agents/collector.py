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

    def add_span(self, span: dict[str, Any]) -> None:
        self.spans.append(span)
