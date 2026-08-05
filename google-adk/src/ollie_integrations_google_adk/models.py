"""ADK execution graph node types (internal capture layer)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionType(str, Enum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"


@dataclass
class AdkExecutionNode:
    """One node in the internal ADK execution span tree."""

    node_id: str
    execution_type: ExecutionType
    name: str
    parent_id: str | None = None
    is_delegation: bool = False
    input_text: str = ""
    output_text: str | None = None
    started_at: str = ""
    ended_at: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    attributes: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    closed: bool = False
