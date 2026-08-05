"""Allowed signal names for normalized run interactions (negative-only defaults)."""

from __future__ import annotations

from typing import Literal

PartitionRole = Literal["execution", "outcome"]

# P1 — surface failures (span-anchored when possible)
RUN_CONTEXT_P1 = frozenset(
    {
        "tool_error",
        "unknown_tool",
        "llm_error",
        "safety_stop",
        "output_truncated",
        "malformed_tool_call",
        "rate_limited",
        "provider_unavailable",
        "tool_loop",
    }
)

# P2 — run / KPI outcomes (interaction-anchored)
RUN_CONTEXT_P2 = frozenset(
    {
        "runtime_failure",
        "empty_final_response",
        "high_latency",
    }
)

RUN_CONTEXT = frozenset(RUN_CONTEXT_P1 | RUN_CONTEXT_P2)
RUN_TRIGGER = frozenset({"repeated_tool_error"})  # P1 execution pattern

# Names seeded into tenant Signal rows for signal_hits persistence.
ALL_ADK_INSTRUMENTED_SIGNALS: tuple[str, ...] = tuple(sorted(RUN_CONTEXT | RUN_TRIGGER))

# partition_role for bipartite P1/P2 (execution vs outcome)
ADK_PARTITION_ROLE: dict[str, PartitionRole] = {
    **{n: "execution" for n in RUN_CONTEXT_P1},
    **{n: "execution" for n in RUN_TRIGGER},
    **{n: "outcome" for n in RUN_CONTEXT_P2},
}


def partition_role_for_adk_signal(name: str) -> PartitionRole | None:
    return ADK_PARTITION_ROLE.get(str(name or "").strip())
