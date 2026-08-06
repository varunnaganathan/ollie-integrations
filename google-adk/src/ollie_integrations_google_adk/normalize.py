"""Normalize ADK collector span tree to a single run wire interaction."""

from __future__ import annotations

import json
from typing import Any

from ollie_integrations_google_adk.collector import ExecutionSpanCollector, utc_now_iso
from ollie_integrations_google_adk.models import AdkExecutionNode, ExecutionType
from ollie_integrations_google_adk.signals.instrument import instrument_interaction

_SPAN_TYPES = frozenset({ExecutionType.TOOL, ExecutionType.LLM, ExecutionType.AGENT})

_LLM_PROP_ATTRS = (
    "token_count",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "thoughts_tokens",
    "finish_reason",
    "error_type",
    "error_code",
    "error_message",
    "llm_error_message",
)
_AGENT_PROP_ATTRS = ("author", "agent_branch")

# Built-in / structural keys — custom attrs must not overwrite these on properties.
_RESERVED_PROP_KEYS = frozenset(
    {
        "kind",
        "name",
        "status",
        "duration_ms",
        "latency_ms",
        "success",
        *_LLM_PROP_ATTRS,
        *_AGENT_PROP_ATTRS,
        "error_type",
    }
)


def _text_io_dict(text: str | None) -> dict[str, Any]:
    s = str(text or "").strip()
    if not s:
        return {}
    return {"text": s}


def _merge_custom_span_properties(node: AdkExecutionNode, props: dict[str, Any]) -> None:
    """Copy non-reserved node attributes into span properties (v0.3.3+)."""
    for a in node.attributes:
        key = str(a.get("name") or "").strip()
        if not key or key in _RESERVED_PROP_KEYS or key in props:
            continue
        props[key] = a.get("value")


def normalize_collector(collector: ExecutionSpanCollector) -> list[dict[str, Any]]:
    """Map internal span tree to a single normalized run interaction."""
    nodes = collector.nodes_in_order()
    if not nodes:
        raise ValueError("collector has no nodes")

    workflow = next((n for n in nodes if n.execution_type == ExecutionType.WORKFLOW), None)
    if workflow is None:
        raise ValueError("collector missing workflow node")

    nodes_by_id = {n.node_id: n for n in nodes}

    def attr_value(node: AdkExecutionNode, name: str) -> Any:
        for a in node.attributes:
            if a.get("name") == name:
                return a.get("value")
        return None

    def parent_span_ref(node: AdkExecutionNode) -> str | None:
        parent_id = node.parent_id
        if not parent_id:
            return None
        parent = nodes_by_id.get(parent_id)
        if parent is None or parent.execution_type == ExecutionType.WORKFLOW:
            return None
        if parent.execution_type not in _SPAN_TYPES:
            return None
        return parent_id

    def node_to_span(node: AdkExecutionNode) -> dict[str, Any]:
        span_type = {
            ExecutionType.TOOL: "tool",
            ExecutionType.LLM: "llm",
            ExecutionType.AGENT: "agent",
        }.get(node.execution_type)
        if span_type is None:
            raise ValueError(f"unexpected span node type: {node.execution_type}")
        status = "success" if node.success else "failure"
        props: dict[str, Any] = {
            "kind": span_type,
            "name": node.name,
            "status": status,
        }
        latency = attr_value(node, "latency_ms")
        if latency is not None:
            props["duration_ms"] = int(latency)

        if node.execution_type == ExecutionType.LLM:
            for key in _LLM_PROP_ATTRS:
                val = attr_value(node, key)
                if val is None:
                    continue
                if key.endswith("_tokens") or key == "token_count":
                    props[key] = int(val)
                else:
                    props[key] = str(val)
        elif node.execution_type == ExecutionType.AGENT:
            for key in _AGENT_PROP_ATTRS:
                val = attr_value(node, key)
                if val is not None and str(val).strip():
                    props[key] = str(val)
        else:
            err_type = attr_value(node, "error_type")
            if err_type is not None:
                props["error_type"] = str(err_type)

        _merge_custom_span_properties(node, props)

        span: dict[str, Any] = {
            "type": span_type,
            "name": node.name,
            "status": status,
            "span_ref": node.node_id,
            "started_at": node.started_at,
            "ended_at": node.ended_at or node.started_at,
            "input": _text_io_dict(node.input_text if collector.capture_content else ""),
            "output": _text_io_dict(node.output_text if collector.capture_content else ""),
            "properties": props,
        }
        pref = parent_span_ref(node)
        if pref:
            span["parent_span_ref"] = pref
        # Keep lean fields for validate / older readers
        if latency is not None:
            span["duration_ms"] = int(latency)
        for key in ("token_count", "prompt_tokens", "completion_tokens", "finish_reason", "error_type", "error_code", "error_message"):
            if key in props:
                span[key] = props[key]
        return span

    all_spans: list[dict[str, Any]] = []
    for node in nodes:
        if node.execution_type in _SPAN_TYPES:
            all_spans.append(node_to_span(node))

    tool_names = [s["name"] for s in all_spans if s.get("type") == "tool"]
    run_attrs = list(workflow.attributes)
    # Raindrop-parity run-level tool bag (overwrite if already present).
    # tool_call_names is a JSON string so it validates as a registered categorical feature.
    run_attrs = [a for a in run_attrs if a.get("name") not in ("tool_calls_count", "tool_call_names")]
    run_attrs.append({"name": "tool_calls_count", "value": len(tool_names)})
    run_attrs.append({"name": "tool_call_names", "value": json.dumps(list(tool_names))})

    wf_success = workflow.success and collector.status != "failed"
    child_ok = all(s.get("status") != "failure" for s in all_spans)
    run_success = wf_success and child_ok

    wf_latency = attr_value(workflow, "latency_ms")
    run_events, signal_hits = instrument_interaction(
        interaction_type="run",
        spans=all_spans,
        output=workflow.output_text,
        success=run_success,
        latency_ms=int(wf_latency) if wf_latency is not None else 0,
        interaction_ref="ix_0",
    )

    return [
        {
            "interaction_type": "run",
            "name": workflow.name,
            "input": workflow.input_text,
            "output": workflow.output_text,
            "events": run_events,
            "_signal_hits": signal_hits,
            "attributes": run_attrs,
            "started_at": workflow.started_at,
            "ended_at": workflow.ended_at or utc_now_iso(),
        }
    ]
