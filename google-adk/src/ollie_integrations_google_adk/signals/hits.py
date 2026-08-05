"""Anchored signal hit helpers (Emergent warehouse shape)."""

from __future__ import annotations

from typing import Any, Literal

from ollie_integrations_google_adk.signals.catalog import RUN_CONTEXT_P1, RUN_TRIGGER
from ollie_integrations_google_adk.signals.direct import (
    MALFORMED_FINISH,
    RATE_LIMIT_CODES,
    SAFETY_FINISH,
    TRUNCATED_FINISH,
    UNAVAILABLE_CODES,
)

AnchorKind = Literal["span", "interaction"]

# P1 surface failures — prefer concrete span anchors.
_SPAN_ANCHORED = frozenset(RUN_CONTEXT_P1 | RUN_TRIGGER)

_INTERACTION_ONLY = frozenset(
    {
        "runtime_failure",
        "empty_final_response",
        "high_latency",
    }
)


def make_signal_hit(
    *,
    signal: str,
    kind: str,
    anchor_kind: AnchorKind,
    anchor_id: str,
) -> dict[str, Any]:
    return {
        "signal": str(signal).strip(),
        "kind": str(kind).strip(),
        "anchor_kind": anchor_kind,
        "anchor_id": str(anchor_id).strip(),
    }


def _finish_reason(sp: dict[str, Any]) -> str:
    fr = sp.get("finish_reason")
    if fr is None and isinstance(sp.get("properties"), dict):
        fr = sp["properties"].get("finish_reason")
    return str(fr or "").lower()


def _error_code(sp: dict[str, Any]) -> str:
    code = sp.get("error_code")
    if code is None and isinstance(sp.get("properties"), dict):
        code = sp["properties"].get("error_code")
    return str(code or "").lower()


def hits_from_named_signals(
    *,
    trigger: list[dict[str, Any]],
    context: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    interaction_ref: str,
) -> list[dict[str, Any]]:
    """Convert {name: ...} detector outputs into anchored _signal_hits rows."""
    spans_by_name: dict[str, list[dict[str, Any]]] = {}
    for sp in spans:
        if not isinstance(sp, dict):
            continue
        n = str(sp.get("name") or "").strip()
        if n:
            spans_by_name.setdefault(n, []).append(sp)

    tool_spans = [s for s in spans if str(s.get("type") or "") == "tool"]
    failed_tools = [s for s in tool_spans if str(s.get("status") or "") == "failure"]
    llm_spans = [s for s in spans if str(s.get("type") or "") == "llm"]

    pending: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append(sig: dict[str, Any], kind: str) -> None:
        name = str(sig.get("name") or "").strip()
        if not name or name in seen:
            return
        seen.add(name)

        if name in _INTERACTION_ONLY or name not in _SPAN_ANCHORED:
            pending.append(
                make_signal_hit(
                    signal=name,
                    kind=kind,
                    anchor_kind="interaction",
                    anchor_id=interaction_ref,
                )
            )
            return

        anchor_kind: AnchorKind = "span"
        anchor_id = ""

        if name in ("tool_error", "unknown_tool"):
            tool = str(sig.get("tool") or "").strip()
            for sp in spans_by_name.get(tool, []) or failed_tools:
                if str(sp.get("type") or "") == "tool" and str(sp.get("status") or "") == "failure":
                    anchor_id = str(sp.get("span_ref") or "")
                    if anchor_id:
                        break
        elif name == "repeated_tool_error":
            if failed_tools:
                anchor_id = str(failed_tools[0].get("span_ref") or "")
        elif name == "tool_loop":
            tool = str(sig.get("tool") or "").strip()
            candidates = spans_by_name.get(tool, []) if tool else []
            if not candidates and tool_spans:
                candidates = [tool_spans[-1]]
            for sp in candidates:
                if str(sp.get("type") or "") == "tool":
                    anchor_id = str(sp.get("span_ref") or "")
                    if anchor_id:
                        break
        elif name in (
            "llm_error",
            "safety_stop",
            "output_truncated",
            "malformed_tool_call",
            "rate_limited",
            "provider_unavailable",
        ):
            llm = str(sig.get("llm") or "").strip()
            candidates = spans_by_name.get(llm, []) if llm else list(llm_spans)
            for sp in candidates:
                if str(sp.get("type") or "") != "llm":
                    continue
                fr = _finish_reason(sp)
                code = _error_code(sp)
                status = str(sp.get("status") or "")
                if name == "llm_error" and (
                    status == "failure" or code in RATE_LIMIT_CODES or code in UNAVAILABLE_CODES
                ):
                    anchor_id = str(sp.get("span_ref") or "")
                    break
                if name == "safety_stop" and fr in SAFETY_FINISH:
                    anchor_id = str(sp.get("span_ref") or "")
                    break
                if name == "output_truncated" and fr in TRUNCATED_FINISH:
                    anchor_id = str(sp.get("span_ref") or "")
                    break
                if name == "malformed_tool_call" and fr in MALFORMED_FINISH:
                    anchor_id = str(sp.get("span_ref") or "")
                    break
                if name == "rate_limited" and code in RATE_LIMIT_CODES:
                    anchor_id = str(sp.get("span_ref") or "")
                    break
                if name == "provider_unavailable" and code in UNAVAILABLE_CODES:
                    anchor_id = str(sp.get("span_ref") or "")
                    break
            if not anchor_id and name == "llm_error":
                for sp in llm_spans:
                    if str(sp.get("status") or "") == "failure":
                        anchor_id = str(sp.get("span_ref") or "")
                        break

        if not anchor_id:
            anchor_kind = "interaction"
            anchor_id = interaction_ref

        pending.append(
            make_signal_hit(signal=name, kind=kind, anchor_kind=anchor_kind, anchor_id=anchor_id)
        )

    for sig in trigger:
        if isinstance(sig, dict):
            _append(sig, "trigger")
    for sig in context:
        if isinstance(sig, dict):
            _append(sig, "context")
    return pending
