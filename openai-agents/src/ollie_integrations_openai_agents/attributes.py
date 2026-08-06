"""Attach custom interaction / span attributes during an active OpenAI Agents run."""

from __future__ import annotations

from typing import Any

from ollie_integrations_openai_agents.collector import RunCollector


def add_interaction_attributes(attributes: dict[str, Any]) -> None:
    """Add custom attributes to the active run interaction.

    Call while ``Runner.run`` / ``run_sync`` is in flight (tool body, hook, middleware).
    Register non-built-in names once via ``client.define_feature(...)`` before ingest.
    Available in ``ollie-integrations-openai-agents`` **0.2.2+**.
    """
    collector = RunCollector.current()
    if collector is None or not attributes:
        return
    collector.merge_run_attributes(attributes)


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """Add custom properties to the current open span (tool / llm / agent / …).

    Call while that span is open (e.g. inside a ``@function_tool`` body). No-op if
    there is no collector or no open span. Available in **0.2.2+**. Does not require
    ``define_feature`` (span ``properties``, not run features).
    """
    collector = RunCollector.current()
    if collector is None or not attributes:
        return
    collector.merge_pending_span_attributes(attributes)
