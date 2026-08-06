"""Anchored signal hit helpers (Emergent warehouse shape)."""

from __future__ import annotations

from typing import Any, Literal

AnchorKind = Literal["span", "interaction"]

_SPAN_ANCHORED = frozenset(
    {
        "tool_error",
        "llm_error",
        "safety_stop",
        "output_truncated",
        "guardrail_blocked",
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

    pending: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append(sig: dict[str, Any], kind: str) -> None:
        name = str(sig.get("name") or "").strip()
        if not name or name in seen:
            return
        seen.add(name)
        if name in _SPAN_ANCHORED:
            anchor_kind: AnchorKind = "span"
            anchor_id = ""
            if name == "tool_error":
                tool = str(sig.get("tool") or "").strip()
                for sp in spans_by_name.get(tool, []) or [
                    s for s in spans if str(s.get("type") or "") == "tool" and s.get("status") == "failure"
                ]:
                    anchor_id = str(sp.get("span_ref") or "")
                    if anchor_id:
                        break
            elif name == "llm_error":
                llm = str(sig.get("llm") or "").strip()
                for sp in spans_by_name.get(llm, []) or [
                    s for s in spans if str(s.get("type") or "") == "llm" and s.get("status") == "failure"
                ]:
                    anchor_id = str(sp.get("span_ref") or "")
                    if anchor_id:
                        break
            elif name == "guardrail_blocked":
                gr = str(sig.get("guardrail") or "").strip()
                for sp in spans_by_name.get(gr, []) or [
                    s for s in spans if str(s.get("type") or "") == "guardrail"
                ]:
                    anchor_id = str(sp.get("span_ref") or "")
                    if anchor_id:
                        break
            elif name in ("safety_stop", "output_truncated"):
                for sp in spans:
                    if str(sp.get("type") or "") != "llm":
                        continue
                    props = sp.get("properties") if isinstance(sp.get("properties"), dict) else {}
                    fr = str(sp.get("finish_reason") or props.get("finish_reason") or "").lower()
                    if name == "safety_stop" and fr in ("safety", "content_filter", "content_filtered"):
                        anchor_id = str(sp.get("span_ref") or "")
                        break
                    if name == "output_truncated" and fr in ("length", "max_tokens", "max_output_tokens"):
                        anchor_id = str(sp.get("span_ref") or "")
                        break
            if not anchor_id:
                anchor_kind = "interaction"
                anchor_id = interaction_ref
        else:
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
