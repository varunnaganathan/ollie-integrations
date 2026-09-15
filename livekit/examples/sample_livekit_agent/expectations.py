"""Expected turn+span shape for sample_livekit_agent."""

from __future__ import annotations

from typing import Any

APP_NAME = "sample_livekit_agent"
AGENT_NAME = "support_agent"
TOOL_NAME = "lookup_weather"
VOICE_NAMES = ("stt", "turn_detection", "tts")
MIN_TURNS = 1
MIN_SPANS_PER_TURN = 4  # stt, td, agent, tts (tool/llm optional)


def _all_spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        events = ix.get("events")
        if isinstance(events, dict):
            for sp in events.get("spans") or []:
                if isinstance(sp, dict):
                    spans.append(sp)
    return spans


def assert_expected_names(payload: dict[str, Any]) -> None:
    wf = payload.get("workflow") or {}
    if str(wf.get("name") or "") != APP_NAME:
        raise AssertionError(f"workflow.name expected {APP_NAME!r}, got {wf.get('name')!r}")

    span_names = {sp.get("name") for sp in _all_spans(payload)}
    for expected in (AGENT_NAME, TOOL_NAME, *VOICE_NAMES):
        if expected not in span_names:
            raise AssertionError(f"missing span name {expected!r}; got {sorted(span_names)}")


def assert_min_interaction_count(payload: dict[str, Any], *, minimum: int = MIN_TURNS) -> None:
    count = len(payload.get("interactions") or [])
    if count < minimum:
        raise AssertionError(f"expected at least {minimum} turn interactions, got {count}")


def assert_min_span_coverage(payload: dict[str, Any]) -> None:
    for ix in payload.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        events = ix.get("events") if isinstance(ix.get("events"), dict) else {}
        spans = events.get("spans") or []
        if len(spans) < MIN_SPANS_PER_TURN:
            raise AssertionError(
                f"turn {ix.get('name')}: expected ≥{MIN_SPANS_PER_TURN} spans, got {len(spans)}"
            )
