"""Promote lean spans to warehouse interiors (input/output/properties)."""

from __future__ import annotations

from typing import Any

_PROP_KEYS = (
    "duration_ms",
    "token_count",
    "finish_reason",
    "error_type",
    "triggered",
    "from_agent",
    "to_agent",
)


def warehouse_shape_span(span: dict[str, Any]) -> dict[str, Any]:
    """Ensure span has input/output/properties; keep validate fields."""
    if not isinstance(span, dict):
        return span
    out = dict(span)
    span_type = str(out.get("type") or "").strip() or "unknown"
    name = str(out.get("name") or "").strip() or span_type
    status = str(out.get("status") or "success").strip() or "success"

    props = dict(out.get("properties") or {}) if isinstance(out.get("properties"), dict) else {}
    # Preserve custom properties already set (e.g. from add_span_attributes); fill builtins.
    props.setdefault("kind", span_type)
    props.setdefault("name", name)
    props.setdefault("status", status)
    for key in _PROP_KEYS:
        if key in out and out[key] is not None:
            props.setdefault(key, out[key])
    out["properties"] = props

    if not isinstance(out.get("input"), dict):
        out["input"] = {}
    if not isinstance(out.get("output"), dict):
        out["output"] = {}
    return out


def warehouse_shape_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [warehouse_shape_span(s) for s in spans if isinstance(s, dict)]


def drop_orphan_parent_span_refs(
    spans: list[dict[str, Any]],
    *,
    interaction_ref: str = "ix_0",
) -> list[dict[str, Any]]:
    """Drop parent_span_ref values that ingest cannot resolve in this interaction."""
    refs = {
        str(s.get("span_ref")).strip()
        for s in spans
        if isinstance(s, dict) and str(s.get("span_ref") or "").strip()
    }
    allowed = set(refs)
    if interaction_ref:
        allowed.add(str(interaction_ref).strip())
    for span in spans:
        if not isinstance(span, dict):
            continue
        parent = span.get("parent_span_ref")
        if parent is None or not str(parent).strip():
            continue
        if str(parent).strip() not in allowed:
            span.pop("parent_span_ref", None)
    return spans
