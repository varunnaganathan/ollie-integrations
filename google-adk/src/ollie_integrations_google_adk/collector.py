"""In-memory ADK execution span tree."""

from __future__ import annotations

import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from ollie_integrations_google_adk.models import AdkExecutionNode, ExecutionType

_current_collector: ContextVar[ExecutionSpanCollector | None] = ContextVar(
    "ollie_adk_collector", default=None
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionSpanCollector:
    """Collect Workflow / Agent / Tool / LLM nodes for one ADK invocation."""

    def __init__(
        self,
        *,
        app_name: str,
        session_id: str | None = None,
        capture_content: bool = True,
    ) -> None:
        self.app_name = app_name
        self.session_id = session_id
        self.capture_content = capture_content
        self._nodes: dict[str, AdkExecutionNode] = {}
        self._order: list[str] = []
        self._stack: list[str] = []
        self._seq = 0
        self.workflow_id: str | None = None
        self.invocation_id: str | None = None
        self.status: str = "completed"

    @classmethod
    def current(cls) -> ExecutionSpanCollector | None:
        return _current_collector.get()

    @classmethod
    def set_current(cls, collector: ExecutionSpanCollector | None) -> None:
        _current_collector.set(collector)

    def _next_id(self) -> str:
        nid = f"n_{self._seq}"
        self._seq += 1
        return nid

    def open_node(
        self,
        execution_type: ExecutionType,
        name: str,
        *,
        parent_id: str | None = None,
        input_text: str = "",
        is_delegation: bool = False,
        extra_events: list[dict[str, Any]] | None = None,
    ) -> str:
        if parent_id is None and self._stack:
            parent_id = self._stack[-1]
        nid = self._next_id()
        started = utc_now_iso()
        node = AdkExecutionNode(
            node_id=nid,
            execution_type=execution_type,
            name=name,
            parent_id=parent_id,
            is_delegation=is_delegation,
            input_text=input_text if self.capture_content else "",
            started_at=started,
        )
        if not self.capture_content:
            node.events.append(
                {
                    "name": "adk.content_redacted",
                    "at": started,
                    "payload": {"execution_type": execution_type.value},
                }
            )
        for ev in extra_events or []:
            node.events.append(ev)
        self._nodes[nid] = node
        self._order.append(nid)
        self._stack.append(nid)
        if execution_type == ExecutionType.WORKFLOW:
            self.workflow_id = nid
        return nid

    def add_event(self, node_id: str, name: str, *, payload: dict[str, Any] | None = None) -> None:
        node = self._nodes.get(node_id)
        if not node:
            return
        entry: dict[str, Any] = {"name": name, "at": utc_now_iso()}
        if payload:
            entry["payload"] = payload
        node.events.append(entry)

    def add_attributes(self, node_id: str, attributes: dict[str, Any]) -> None:
        """Merge custom attributes onto an open node (used by add_interaction_attributes)."""
        node = self._nodes.get(node_id)
        if not node or not attributes:
            return
        for name, value in attributes.items():
            key = str(name or "").strip()
            if not key:
                continue
            node.attributes = [a for a in node.attributes if a.get("name") != key]
            node.attributes.append({"name": key, "value": value})

    def close_node(
        self,
        node_id: str,
        *,
        output_text: str | None = None,
        success: bool = True,
        attributes: list[dict[str, Any]] | None = None,
        extra_events: list[dict[str, Any]] | None = None,
    ) -> None:
        node = self._nodes.get(node_id)
        if not node or node.closed:
            return
        node.ended_at = utc_now_iso()
        node.success = success
        if output_text is not None and self.capture_content:
            node.output_text = output_text
        elif output_text is not None and not self.capture_content:
            node.output_text = ""
        if attributes:
            node.attributes.extend(attributes)
        started_ts = _parse_iso(node.started_at)
        ended_ts = _parse_iso(node.ended_at)
        if started_ts and ended_ts:
            ms = max(0, int((ended_ts - started_ts) * 1000))
            if not any(a.get("name") == "latency_ms" for a in node.attributes):
                node.attributes.append({"name": "latency_ms", "value": ms})
        if not any(a.get("name") == "success" for a in node.attributes):
            node.attributes.append({"name": "success", "value": success})
        for ev in extra_events or []:
            node.events.append(ev)
        node.closed = True
        if self._stack and self._stack[-1] == node_id:
            self._stack.pop()
        elif node_id in self._stack:
            self._stack = [x for x in self._stack if x != node_id]

    def current_node_id(self) -> str | None:
        return self._stack[-1] if self._stack else None

    def current_span_id(self) -> str | None:
        """Innermost open tool / llm / agent node (skips workflow)."""
        for nid in reversed(self._stack):
            node = self._nodes.get(nid)
            if node is not None and node.execution_type in (
                ExecutionType.TOOL,
                ExecutionType.LLM,
                ExecutionType.AGENT,
            ):
                return nid
        return None

    def current_agent_id(self) -> str | None:
        for nid in reversed(self._stack):
            node = self._nodes[nid]
            if node.execution_type == ExecutionType.AGENT:
                return nid
        return None

    def nodes_in_order(self) -> list[AdkExecutionNode]:
        return [self._nodes[nid] for nid in self._order if nid in self._nodes]

    def open_workflow(self, *, input_text: str = "") -> str:
        return self.open_node(
            ExecutionType.WORKFLOW,
            self.app_name,
            parent_id=None,
            input_text=input_text,
        )

    def open_agent(
        self,
        name: str,
        *,
        input_text: str = "",
        is_delegation: bool = False,
        agent_branch: str | None = None,
        author: str | None = None,
    ) -> str:
        parent = self.workflow_id if self.workflow_id else None
        if self.current_agent_id() and is_delegation:
            parent = self.current_agent_id()
        extra: list[dict[str, Any]] | None = None
        if is_delegation:
            extra = [{"name": "adk.delegation", "at": utc_now_iso(), "payload": {"target_agent": name}}]
        nid = self.open_node(
            ExecutionType.AGENT,
            name,
            parent_id=parent,
            input_text=input_text,
            is_delegation=is_delegation,
            extra_events=extra,
        )
        attrs: dict[str, Any] = {"author": str(author or name)}
        if agent_branch is not None and str(agent_branch).strip():
            attrs["agent_branch"] = str(agent_branch).strip()
        self.add_attributes(nid, attrs)
        return nid

    def close_agent(self, node_id: str, *, output_text: str | None = None, success: bool = True) -> None:
        self.close_node(node_id, output_text=output_text, success=success)

    def open_tool(self, name: str, *, input_text: str = "") -> str:
        parent = self.current_agent_id() or self.workflow_id
        return self.open_node(
            ExecutionType.TOOL,
            name,
            parent_id=parent,
            input_text=input_text,
        )

    def close_tool(
        self,
        node_id: str,
        *,
        output_text: str | None = None,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        attrs: list[dict[str, Any]] = []
        if error_type:
            attrs.append({"name": "error_type", "value": str(error_type)})
        payload: dict[str, Any] = {"success": success}
        if error_type:
            payload["error_type"] = error_type
        extra = [{"name": "adk.tool_errored" if not success else "adk.tool_completed", "at": utc_now_iso(), "payload": payload}]
        self.close_node(node_id, output_text=output_text, success=success, attributes=attrs, extra_events=extra)

    def open_llm(self, name: str, *, input_text: str = "") -> str:
        parent = self.current_agent_id() or self.workflow_id
        return self.open_node(
            ExecutionType.LLM,
            name,
            parent_id=parent,
            input_text=input_text,
        )

    def close_llm(
        self,
        node_id: str,
        *,
        output_text: str | None = None,
        success: bool = True,
        token_count: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cached_tokens: int | None = None,
        thoughts_tokens: int | None = None,
        finish_reason: str | None = None,
        error_code: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        attrs: list[dict[str, Any]] = []
        if token_count is not None:
            attrs.append({"name": "token_count", "value": int(token_count)})
        if prompt_tokens is not None:
            attrs.append({"name": "prompt_tokens", "value": int(prompt_tokens)})
        if completion_tokens is not None:
            attrs.append({"name": "completion_tokens", "value": int(completion_tokens)})
        if cached_tokens is not None:
            attrs.append({"name": "cached_tokens", "value": int(cached_tokens)})
        if thoughts_tokens is not None:
            attrs.append({"name": "thoughts_tokens", "value": int(thoughts_tokens)})
        if finish_reason:
            attrs.append({"name": "finish_reason", "value": str(finish_reason)})
        if error_code:
            attrs.append({"name": "error_code", "value": str(error_code)})
        if error_type:
            attrs.append({"name": "error_type", "value": str(error_type)})
        if error_message:
            attrs.append({"name": "error_message", "value": str(error_message)})
            attrs.append({"name": "llm_error_message", "value": str(error_message)})
        payload: dict[str, Any] = {"success": success}
        if finish_reason:
            payload["finish_reason"] = finish_reason
        if token_count is not None:
            payload["token_count"] = token_count
        if prompt_tokens is not None:
            payload["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            payload["completion_tokens"] = completion_tokens
        if cached_tokens is not None:
            payload["cached_tokens"] = cached_tokens
        if thoughts_tokens is not None:
            payload["thoughts_tokens"] = thoughts_tokens
        if error_code:
            payload["error_code"] = error_code
        if error_type:
            payload["error_type"] = error_type
        if error_message:
            payload["error_message"] = error_message
        ev = (
            "adk.generation_blocked"
            if not success and (finish_reason or error_code or error_message)
            else "adk.generation_completed"
        )
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            attributes=attrs,
            extra_events=[{"name": ev, "at": utc_now_iso(), "payload": payload}],
        )


def _parse_iso(s: str) -> float | None:
    if not s:
        return None
    try:
        from dateutil.parser import parse as duparse

        dt = duparse(s.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()
