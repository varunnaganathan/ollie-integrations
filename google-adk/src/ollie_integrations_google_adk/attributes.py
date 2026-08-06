"""Attach custom interaction / span attributes during an active ADK run."""

from __future__ import annotations

from typing import Any

from ollie_integrations_google_adk.collector import ExecutionSpanCollector
from ollie_integrations_google_adk.models import ExecutionType


def add_interaction_attributes(
    attributes: dict[str, Any],
    *,
    interaction: str = "run",
) -> None:
    """Add custom attributes to the active run or agent node.

    Call from tool code or callbacks while ``Runner.run_async`` is in flight.
    Register non-built-in names once via ``client.define_feature(...)`` before ingest.

    ``interaction`` — ``run`` (default, workflow root) or ``agent`` (current agent node).
    Agent-scoped keys land on that agent span's ``properties`` (v0.3.3+).
    """
    collector = ExecutionSpanCollector.current()
    if collector is None or not attributes:
        return
    if interaction == "agent":
        node_id = collector.current_agent_id() or collector.workflow_id
    else:
        node_id = collector.workflow_id
    if not node_id:
        return
    collector.add_attributes(node_id, attributes)


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """Add custom properties to the current open span (tool / llm / agent).

    Call while that span is on the stack (e.g. inside a tool body). No-op if there
    is no collector or no open span. Available in ``ollie-integrations-google-adk``
    **0.3.3+**. Does not require ``define_feature`` (span ``properties``, not run features).
    """
    collector = ExecutionSpanCollector.current()
    if collector is None or not attributes:
        return
    node_id = collector.current_span_id()
    if not node_id:
        return
    collector.add_attributes(node_id, attributes)
