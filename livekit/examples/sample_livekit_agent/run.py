#!/usr/bin/env python3
"""Run sample LiveKit agent with Ollie instrumentation."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_PKG = Path(__file__).resolve().parents[2]
_REPO = _PKG.parent.parent
for _env in (_REPO / ".env", _REPO / "ollie_sentry_backend" / ".env"):
    if _env.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(_env)
        except ImportError:
            pass
        break

if str(_PKG / "examples") not in sys.path:
    sys.path.insert(0, str(_PKG / "examples"))

from sample_livekit_agent.agent import (  # noqa: E402
    AGENT_NAME,
    APP_NAME,
    TOOL_NAME,
    USER_MESSAGE,
    build_agent,
)
from sample_livekit_agent.expectations import assert_expected_names, assert_min_interaction_count  # noqa: E402

DEFAULT_LIVE_TIMEOUT_S = 90


def _mock_client() -> Any:
    client = MagicMock()
    client.agent_id = os.getenv("OLLIE_AGENT_ID", "agent_livekit_sample")
    client._transport = MagicMock()
    client._transport.validate_trace.return_value = {"accepted": True}
    client._transport.process_trace.return_value = {"accepted": True}
    client._transport.ingest_trace.return_value = {"accepted": True}
    client._delivery = MagicMock()
    return client


def run_once_synthetic(*, local_only: bool = True, flush_mode: str = "validate") -> dict[str, Any]:
    """Offline smoke: build span tree manually (does not exercise LiveKit hooks)."""
    if local_only:
        os.environ.setdefault("OLLIE_API_KEY", "local-test-key")
        os.environ.setdefault("OLLIE_AGENT_ID", "agent_livekit_sample")

    from ollie_integrations_livekit import attach_ollie, get_last_wire_payload
    from ollie_integrations_livekit.collector import ExecutionSpanCollector
    from ollie_integrations_livekit.emit import collector_to_wire_payload, flush_collector_to_client

    client = _mock_client()
    attach_ollie(client, app_name=APP_NAME, flush_mode=flush_mode)

    collector = ExecutionSpanCollector(
        app_name=APP_NAME,
        session_id="sess-text-smoke",
        room="room-smoke",
    )
    ExecutionSpanCollector.set_current(collector)
    session_id = collector.open_agent_session(input_text="session_start room=room-smoke")
    turn = collector.open_user_turn(input_text=USER_MESSAGE)
    stt = collector.open_stt(input_text="[user_audio]")
    collector.close_stt(stt, output_text=USER_MESSAGE, success=True)
    td = collector.open_turn_detection(input_text=USER_MESSAGE)
    collector.close_turn_detection(td, output_text="turn_complete", success=True)
    ag = collector.open_agent(AGENT_NAME, input_text=USER_MESSAGE)
    collector.add_event(ag, "livekit.llm_start")
    tool = collector.open_tool(TOOL_NAME, input_text='{"city": "NYC"}')
    collector.close_tool(tool, output_text='{"temp_f": 72, "condition": "sunny"}', success=True)
    collector.add_event(ag, "livekit.llm_end")
    collector.close_agent(ag, output_text="It's 72°F and sunny in NYC.", success=True)
    tts = collector.open_tts(input_text="It's 72°F and sunny in NYC.")
    collector.close_tts(tts, output_text="[agent_audio]", success=True)
    collector.close_user_turn(turn, output_text="[agent_audio]", success=True)
    collector.close_agent_session(session_id, output_text="session_ended", success=True)

    wire = collector_to_wire_payload(collector, agent_id=client.agent_id, session_id=collector.session_id)
    flush_collector_to_client(collector, client, flush_mode=flush_mode)
    ExecutionSpanCollector.set_current(None)
    return get_last_wire_payload() or wire


async def run_once_live(
    *,
    flush_mode: str = "validate",
    timeout_s: float = DEFAULT_LIVE_TIMEOUT_S,
    user_message: str = USER_MESSAGE,
) -> dict[str, Any]:
    """Live e2e: real AgentSession + attach_ollie hooks + text-mode turn (needs OPENAI_API_KEY)."""
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise RuntimeError("OPENAI_API_KEY required for live LiveKit run")
    os.environ.setdefault("OLLIE_API_KEY", "local-test-key")
    os.environ.setdefault("OLLIE_AGENT_ID", "agent_livekit_sample")

    from livekit.agents.voice import AgentSession
    from livekit.plugins import openai

    from ollie_integrations_livekit import attach_ollie, get_last_wire_payload

    client = _mock_client()
    attach_ollie(client, app_name=APP_NAME, flush_mode=flush_mode)

    session = AgentSession(llm=openai.LLM(model="gpt-4.1-mini"))
    agent = build_agent()

    try:
        await asyncio.wait_for(session.start(agent=agent), timeout=timeout_s)
        run_result = session.run(user_input=user_message, input_modality="text")
        await asyncio.wait_for(run_result, timeout=timeout_s)
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(session.aclose(), timeout=10)

    wire = get_last_wire_payload()
    if wire is None:
        raise RuntimeError("no wire payload captured after live AgentSession run")
    return wire


def run_once_live_sync(
    *,
    flush_mode: str = "validate",
    timeout_s: float = DEFAULT_LIVE_TIMEOUT_S,
) -> dict[str, Any]:
    return asyncio.run(run_once_live(flush_mode=flush_mode, timeout_s=timeout_s))


# Backward-compatible alias for synthetic smoke
run_once = run_once_synthetic


def main() -> int:
    p = argparse.ArgumentParser(description="Sample LiveKit agent with Ollie attach_ollie")
    p.add_argument("--live", action="store_true", help="Run live AgentSession e2e (OPENAI_API_KEY)")
    p.add_argument("--print-tree", action="store_true")
    p.add_argument("--dump-wire", metavar="PATH")
    p.add_argument("--flush-mode", default="validate", choices=("validate", "process", "ingest"))
    p.add_argument("--timeout", type=float, default=DEFAULT_LIVE_TIMEOUT_S)
    args = p.parse_args()

    try:
        if args.live:
            wire = run_once_live_sync(flush_mode=args.flush_mode, timeout_s=args.timeout)
        else:
            wire = run_once_synthetic(local_only=True, flush_mode=args.flush_mode)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    assert_min_interaction_count(wire)
    if not args.live:
        assert_expected_names(wire)

    if args.print_tree:
        from ollie.tree import render_interaction_tree

        print(render_interaction_tree(wire.get("interactions") or []), file=sys.stderr)

    if args.dump_wire:
        Path(args.dump_wire).write_text(json.dumps(wire, indent=2) + "\n")
        print(f"wrote {args.dump_wire}", file=sys.stderr)

    print(json.dumps(wire, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
