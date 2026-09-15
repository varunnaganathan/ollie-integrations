"""In-memory LiveKit execution span tree."""

from __future__ import annotations

import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from ollie_integrations_livekit.models import ExecutionType, LiveKitExecutionNode

_current_collector: ContextVar[ExecutionSpanCollector | None] = ContextVar(
    "ollie_livekit_collector", default=None
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionSpanCollector:
    """Collect AgentSession / UserTurn / STT / TD / Agent / Tool / TTS nodes."""

    def __init__(
        self,
        *,
        app_name: str,
        session_id: str | None = None,
        capture_content: bool = True,
        room: str | None = None,
        participant: str | None = None,
        job_id: str | None = None,
    ) -> None:
        self.app_name = app_name
        self.session_id = session_id
        self.capture_content = capture_content
        self.room = room
        self.participant = participant
        self.job_id = job_id
        self._nodes: dict[str, LiveKitExecutionNode] = {}
        self._order: list[str] = []
        self._stack: list[str] = []
        self._seq = 0
        self.session_node_id: str | None = None
        self.current_turn_id: str | None = None
        self.current_stt_id: str | None = None
        self.current_turn_detection_id: str | None = None
        self.current_agent_id: str | None = None
        self.current_tts_id: str | None = None
        self._turn_count = 0
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
        interaction_type: str | None = None,
        extra_events: list[dict[str, Any]] | None = None,
        attributes: list[dict[str, Any]] | None = None,
    ) -> str:
        if parent_id is None and self._stack:
            parent_id = self._stack[-1]
        nid = self._next_id()
        started = utc_now_iso()
        node = LiveKitExecutionNode(
            node_id=nid,
            execution_type=execution_type,
            name=name,
            parent_id=parent_id,
            interaction_type=interaction_type,
            input_text=input_text if self.capture_content else "",
            started_at=started,
        )
        if attributes:
            node.attributes.extend(attributes)
        node.events.append(node.execution_started_event())
        if not self.capture_content:
            node.events.append(
                {
                    "name": "livekit.content_redacted",
                    "at": started,
                    "payload": {"execution_type": execution_type.value},
                }
            )
        for ev in extra_events or []:
            node.events.append(ev)
        self._nodes[nid] = node
        self._order.append(nid)
        self._stack.append(nid)
        if execution_type == ExecutionType.AGENT_SESSION:
            self.session_node_id = nid
        elif execution_type == ExecutionType.USER_TURN:
            self.current_turn_id = nid
        return nid

    def add_event(self, node_id: str, name: str, *, payload: dict[str, Any] | None = None) -> None:
        node = self._nodes.get(node_id)
        if not node:
            return
        entry: dict[str, Any] = {"name": name, "at": utc_now_iso()}
        if payload:
            entry["payload"] = payload
        node.events.append(entry)

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
        node.events.append(node.execution_completed_event())
        node.closed = True
        if self._stack and self._stack[-1] == node_id:
            self._stack.pop()
        elif node_id in self._stack:
            self._stack = [x for x in self._stack if x != node_id]

    def nodes_in_order(self) -> list[LiveKitExecutionNode]:
        return [self._nodes[nid] for nid in self._order if nid in self._nodes]

    def open_agent_session(self, *, input_text: str = "") -> str:
        attrs: list[dict[str, Any]] = []
        if self.room:
            attrs.append({"name": "room", "value": self.room})
        if self.participant:
            attrs.append({"name": "participant", "value": self.participant})
        if self.job_id:
            attrs.append({"name": "job_id", "value": self.job_id})
        if self.session_id:
            attrs.append({"name": "session_id", "value": self.session_id})
        return self.open_node(
            ExecutionType.AGENT_SESSION,
            self.app_name,
            parent_id=None,
            input_text=input_text,
            interaction_type=None,
            attributes=attrs,
            extra_events=[{"name": "livekit.session_started", "at": utc_now_iso()}],
        )

    def close_agent_session(self, node_id: str, *, output_text: str = "", success: bool = True) -> None:
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            extra_events=[{"name": "livekit.session_ended", "at": utc_now_iso()}],
        )

    def open_user_turn(self, *, input_text: str = "") -> str:
        self._turn_count += 1
        parent = self.session_node_id
        return self.open_node(
            ExecutionType.USER_TURN,
            f"turn_{self._turn_count}",
            parent_id=parent,
            input_text=input_text,
            interaction_type=None,
            extra_events=[{"name": "livekit.turn_started", "at": utc_now_iso()}],
        )

    def close_user_turn(self, node_id: str, *, output_text: str = "", success: bool = True) -> None:
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            extra_events=[{"name": "livekit.turn_completed", "at": utc_now_iso()}],
        )
        if self.current_turn_id == node_id:
            self.current_turn_id = None

    def open_stt(self, name: str = "stt", *, input_text: str = "") -> str:
        parent = self.current_turn_id or self.session_node_id
        nid = self.open_node(
            ExecutionType.STT,
            name,
            parent_id=parent,
            input_text=input_text,
            interaction_type="speech_recognition",
            extra_events=[{"name": "livekit.speech_start", "at": utc_now_iso()}],
        )
        self.current_stt_id = nid
        return nid

    def close_stt(self, node_id: str, *, output_text: str = "", success: bool = True) -> None:
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            extra_events=[
                {"name": "livekit.final_transcript", "at": utc_now_iso()},
                {"name": "livekit.speech_end", "at": utc_now_iso()},
            ],
        )
        if self.current_stt_id == node_id:
            self.current_stt_id = None

    def open_turn_detection(self, *, input_text: str = "") -> str:
        parent = self.current_turn_id or self.session_node_id
        nid = self.open_node(
            ExecutionType.TURN_DETECTION,
            "turn_detection",
            parent_id=parent,
            input_text=input_text,
            interaction_type="turn_management",
            extra_events=[{"name": "livekit.vad_triggered", "at": utc_now_iso()}],
        )
        self.current_turn_detection_id = nid
        return nid

    def close_turn_detection(
        self,
        node_id: str,
        *,
        output_text: str = "turn_complete",
        success: bool = True,
        interrupted: bool = False,
    ) -> None:
        extra: list[dict[str, Any]] = [
            {"name": "livekit.turn_complete", "at": utc_now_iso(), "payload": {"success": success}}
        ]
        if interrupted:
            extra.append({"name": "livekit.interruption", "at": utc_now_iso()})
        self.close_node(node_id, output_text=output_text, success=success, extra_events=extra)
        if self.current_turn_detection_id == node_id:
            self.current_turn_detection_id = None

    def open_agent(
        self,
        name: str,
        *,
        input_text: str = "",
        is_handoff: bool = False,
    ) -> str:
        parent = self.current_turn_id or self.session_node_id
        it = "delegation" if is_handoff else None
        nid = self.open_node(
            ExecutionType.AGENT,
            name,
            parent_id=parent,
            input_text=input_text,
            interaction_type=it,
            extra_events=[{"name": "livekit.agent_enter", "at": utc_now_iso()}],
        )
        self.current_agent_id = nid
        return nid

    def close_agent(self, node_id: str, *, output_text: str = "", success: bool = True) -> None:
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            extra_events=[{"name": "livekit.agent_exit", "at": utc_now_iso()}],
        )
        if self.current_agent_id == node_id:
            self.current_agent_id = None

    def open_tool(self, name: str, *, input_text: str = "") -> str:
        parent = self.current_agent_id or self.current_turn_id or self.session_node_id
        return self.open_node(
            ExecutionType.TOOL,
            name,
            parent_id=parent,
            input_text=input_text,
            interaction_type="external_tool_call",
            extra_events=[{"name": "livekit.tool_start", "at": utc_now_iso()}],
        )

    def close_tool(
        self,
        node_id: str,
        *,
        output_text: str = "",
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        ev_name = "livekit.tool_error" if not success else "livekit.tool_end"
        payload: dict[str, Any] = {"success": success}
        if error_type:
            payload["error_type"] = error_type
        self.close_node(
            node_id,
            output_text=output_text,
            success=success,
            extra_events=[{"name": ev_name, "at": utc_now_iso(), "payload": payload}],
        )

    def open_tts(self, name: str = "tts", *, input_text: str = "") -> str:
        parent = self.current_turn_id or self.session_node_id
        nid = self.open_node(
            ExecutionType.TTS,
            name,
            parent_id=parent,
            input_text=input_text,
            interaction_type="speech_synthesis",
            extra_events=[{"name": "livekit.tts_start", "at": utc_now_iso()}],
        )
        self.current_tts_id = nid
        return nid

    def close_tts(
        self,
        node_id: str,
        *,
        output_text: str = "",
        success: bool = True,
        interrupted: bool = False,
    ) -> None:
        extra: list[dict[str, Any]] = [
            {"name": "livekit.tts_complete", "at": utc_now_iso(), "payload": {"success": success}}
        ]
        if interrupted:
            extra.append({"name": "livekit.interrupted", "at": utc_now_iso()})
        self.close_node(node_id, output_text=output_text, success=success, extra_events=extra)
        if self.current_tts_id == node_id:
            self.current_tts_id = None


def _parse_iso(s: str) -> float | None:
    if not s:
        return None
    try:
        from dateutil.parser import parse as duparse

        dt = duparse(s.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()
