"""LiveKit voice pipeline node types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionType(str, Enum):
    AGENT_SESSION = "agent_session"
    USER_TURN = "user_turn"
    STT = "stt"
    TURN_DETECTION = "turn_detection"
    AGENT = "agent"
    TOOL = "tool"
    TTS = "tts"


@dataclass
class LiveKitExecutionNode:
    """One LiveKit execution unit (session/turn → interaction; stages → spans)."""

    node_id: str
    execution_type: ExecutionType
    name: str
    parent_id: str | None = None
    interaction_type: str | None = None
    input_text: str = ""
    output_text: str | None = None
    started_at: str = ""
    ended_at: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    attributes: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    closed: bool = False

    def execution_started_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"execution_type": self.execution_type.value}
        if self.execution_type == ExecutionType.TOOL:
            payload["livekit_tool_name"] = self.name
        elif self.execution_type == ExecutionType.AGENT:
            payload["livekit_agent_name"] = self.name
        elif self.execution_type == ExecutionType.STT:
            payload["livekit_stt_name"] = self.name
        elif self.execution_type == ExecutionType.TTS:
            payload["livekit_tts_name"] = self.name
        return {
            "name": "livekit.execution_started",
            "at": self.started_at,
            "payload": payload,
        }

    def execution_completed_event(self) -> dict[str, Any]:
        return {
            "name": "livekit.execution_completed",
            "at": self.ended_at,
            "payload": {
                "execution_type": self.execution_type.value,
                "success": self.success,
            },
        }
