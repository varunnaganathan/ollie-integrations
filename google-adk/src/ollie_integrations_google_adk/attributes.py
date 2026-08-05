"""Attach custom interaction attributes during an active ADK run."""

from __future__ import annotations

from typing import Any

from ollie_integrations_google_adk.collector import ExecutionSpanCollector


def add_interaction_attributes(
    attributes: dict[str, Any],
    *,
    interaction: str = "run",
) -> None:
    """Add custom attributes to the active run or agent node.

    Call from tool code or callbacks while ``Runner.run_async`` is in flight.
    Register non-built-in names once via ``client.define_feature(...)`` before ingest.

    ``interaction`` — ``run`` (default, workflow root) or ``agent`` (current agent node).
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
