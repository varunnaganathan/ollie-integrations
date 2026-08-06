"""OpenAI Agents SDK integration for Ollie (single-run model)."""

from ollie_integrations_openai_agents.attributes import (
    add_interaction_attributes,
    add_span_attributes,
)
from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.config import create_ollie_client
from ollie_integrations_openai_agents.emit import collector_to_wire_payload, flush_collector_to_client
from ollie_integrations_openai_agents.hooks import attach_ollie, get_last_wire_payload
from ollie_integrations_openai_agents.normalize import normalize_collector
from ollie_integrations_openai_agents.processor import OllieTracingProcessor, register_processor
from ollie_integrations_openai_agents.version import __version__

__all__ = [
    "__version__",
    "RunCollector",
    "OllieTracingProcessor",
    "add_interaction_attributes",
    "add_span_attributes",
    "attach_ollie",
    "collector_to_wire_payload",
    "create_ollie_client",
    "flush_collector_to_client",
    "get_last_wire_payload",
    "normalize_collector",
    "register_processor",
]
