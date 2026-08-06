#!/usr/bin/env python3
"""Run sample OpenAI Agents workflows with Ollie attach_ollie."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_PKG = Path(__file__).resolve().parents[1]
for _env in (_PKG.parent.parent / ".env", _PKG.parent.parent.parent / ".env"):
    if _env.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(_env, override=False)
        except ImportError:
            pass

if str(_PKG / "examples") not in sys.path:
    sys.path.insert(0, str(_PKG / "examples"))

from sample_openai_agent.agents import build_handoff_agents, build_single_tool_agent  # noqa: E402


def _mock_client() -> Any:
    client = MagicMock()
    client.agent_id = os.getenv("OLLIE_AGENT_ID", "agent_openai_sample")
    client._transport = MagicMock()
    client._transport.validate_trace.return_value = {"accepted": True}
    client._delivery = MagicMock()
    return client


async def run_once(
    mode: str = "single_agent_tool",
    *,
    flush_mode: str = "validate",
    use_mock_client: bool = True,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run sample agent; returns last wire payload (includes session_id when set)."""
    pytest = __import__("pytest")
    pytest.importorskip("agents")

    from agents import Runner
    from ollie_integrations_openai_agents import attach_ollie, create_ollie_client, get_last_wire_payload

    ollie_client = client
    if ollie_client is None:
        ollie_client = _mock_client() if use_mock_client else create_ollie_client()
    attach_ollie(ollie_client, workflow_name="sample_openai_agent", flush_mode=flush_mode)

    if mode == "single_agent_tool":
        agent = build_single_tool_agent()
        await Runner.run(agent, "What's the weather in NYC?")
    elif mode == "multi_agent_handoff":
        triage, _billing = build_handoff_agents()
        await Runner.run(triage, "I need a refund for order 4821")
    else:
        raise ValueError(f"unknown mode: {mode}")

    wire = get_last_wire_payload()
    if wire is None:
        raise RuntimeError("no wire payload captured")
    return wire


async def _run(mode: str, *, flush_mode: str = "validate") -> dict[str, Any]:
    return await run_once(mode, flush_mode=flush_mode, use_mock_client=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("single_agent_tool", "multi_agent_handoff"), default="single_agent_tool")
    p.add_argument("--flush-mode", default="validate", choices=("validate", "process", "ingest"))
    p.add_argument("--live", action="store_true", help="Use real Ollie client (OLLIE_* env)")
    args = p.parse_args()

    try:
        wire = asyncio.run(
            run_once(args.mode, flush_mode=args.flush_mode, use_mock_client=not args.live)
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    assert len(wire.get("interactions") or []) == 1
    ix = wire["interactions"][0]
    assert ix["interaction_type"] == "run"
    assert isinstance(ix["input"], str)
    print(json.dumps(wire, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
