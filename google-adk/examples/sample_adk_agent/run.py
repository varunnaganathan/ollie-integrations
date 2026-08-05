#!/usr/bin/env python3
"""Run sample Google ADK agent with Ollie instrumentation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_PKG = Path(__file__).resolve().parents[2]
_REPO = _PKG.parent.parent
for _env in (_REPO / ".env", _REPO / "ollie_sentry_backend" / ".env"):
    if _env.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(_env, override=False)
        except ImportError:
            pass

if str(_PKG / "examples") not in sys.path:
    sys.path.insert(0, str(_PKG / "examples"))

from sample_adk_agent.agent import APP_NAME, build_runner, default_message_for_mode, user_content  # noqa: E402
from sample_adk_agent.expectations import (  # noqa: E402
    assert_delegation_wire,
    assert_loop_wire,
    assert_normalized_shape,
    assert_parallel_wire,
    assert_sequential_wire,
    assert_single_agent_wire,
)

TOPOLOGY_MODES = ("single", "sequential", "parallel", "loop", "delegation")

_TOPOLOGY_ASSERTERS = {
    "single": assert_single_agent_wire,
    "sequential": assert_sequential_wire,
    "parallel": assert_parallel_wire,
    "loop": assert_loop_wire,
    "delegation": assert_delegation_wire,
}


def _ensure_google_credentials() -> None:
    gemini = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"')
    if gemini:
        os.environ.setdefault("GOOGLE_API_KEY", gemini)
        os.environ.setdefault("GOOGLE_GENAI_API_KEY", gemini)


def _mock_client() -> Any:
    """Test/demo client — same attach_ollie path as production; ingest is mocked."""
    client = MagicMock()
    client.agent_id = os.getenv("OLLIE_AGENT_ID", "agent_adk_sample")
    client._transport = MagicMock()
    client._transport.validate_trace.return_value = {"accepted": True}
    client._transport.process_trace.return_value = {"accepted": True}
    client._transport.ingest_trace.return_value = {"accepted": True}
    client._delivery = MagicMock()
    return client


def _attach_and_prepare(
    *,
    mode: str,
    flush_mode: str,
    use_mock_client: bool,
    client: Any | None,
) -> tuple[Any, Any, str]:
    from ollie_integrations_google_adk import attach_ollie

    ollie_client = client if client is not None else (_mock_client() if use_mock_client else None)
    if ollie_client is None:
        import ollie

        ollie_client = ollie.Client()

    attach_ollie(
        ollie_client,
        app_name=APP_NAME,
        flush_mode=flush_mode,
    )

    runner = build_runner(mode=mode)
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    return runner, ollie_client, session_id


async def _run_adk(
    *,
    mode: str,
    flush_mode: str,
    message: str,
    use_mock_client: bool = True,
    client: Any | None = None,
    use_sync: bool = False,
) -> dict[str, Any]:
    pytest = __import__("pytest")
    pytest.importorskip("google.adk")

    from ollie_integrations_google_adk import get_last_wire_payload

    runner, _ollie_client, session_id = _attach_and_prepare(
        mode=mode,
        flush_mode=flush_mode,
        use_mock_client=use_mock_client,
        client=client,
    )
    await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id="user-sample",
        session_id=session_id,
    )
    if use_sync:
        # Sync path: ADK Runner.run delegates to run_async on a worker thread.
        for _event in runner.run(
            user_id="user-sample",
            session_id=session_id,
            new_message=user_content(message),
        ):
            pass
    else:
        async for _event in runner.run_async(
            user_id="user-sample",
            session_id=session_id,
            new_message=user_content(message),
        ):
            pass

    wire = get_last_wire_payload()
    if wire is None:
        raise RuntimeError("no wire payload captured after run" + ("_async" if not use_sync else ""))
    return wire


def run_once(
    *,
    mode: str = "sequential",
    local_only: bool = True,
    flush_mode: str = "validate",
    message: str | None = None,
    use_mock_client: bool = True,
    client: Any | None = None,
    max_attempts: int = 3,
    use_sync: bool = False,
) -> dict[str, Any]:
    """Run one live ADK invocation and return the v2 wire payload."""
    _ensure_google_credentials()
    if local_only:
        os.environ.setdefault("OLLIE_API_KEY", "adk-e2e-key-1")
        os.environ.setdefault("OLLIE_AGENT_ID", "agent_adk_e2e_1")
        os.environ.setdefault("OLLIE_INGEST_BASE_URL", "http://127.0.0.1:8002")
        os.environ.setdefault("OLLIE_BASE_URL", "http://127.0.0.1:8001")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY") or "").strip():
        raise RuntimeError(
            "GOOGLE_API_KEY, GOOGLE_GENAI_API_KEY, or GEMINI_API_KEY required for live ADK run"
        )
    if message is None:
        message = default_message_for_mode(mode)

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return asyncio.run(
                _run_adk(
                    mode=mode,
                    flush_mode=flush_mode,
                    message=message,
                    use_mock_client=use_mock_client,
                    client=client,
                    use_sync=use_sync,
                )
            )
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts or not _is_transient_gemini_error(exc):
                raise
            import time

            time.sleep(min(60, 15 * (attempt + 1)))
    raise last_exc  # pragma: no cover


def _is_transient_gemini_error(exc: BaseException) -> bool:
    if isinstance(exc, ExceptionGroup):
        return any(_is_transient_gemini_error(e) for e in exc.exceptions)
    name = type(exc).__name__
    if name in ("ClientError", "ServerError", "_ResourceExhaustedError"):
        return True
    msg = str(exc)
    return "429" in msg or "503" in msg or "RESOURCE_EXHAUSTED" in msg or "UNAVAILABLE" in msg


def main() -> int:
    p = argparse.ArgumentParser(description="Sample ADK agent with Ollie attach_ollie")
    p.add_argument("--mode", choices=TOPOLOGY_MODES, default="sequential")
    p.add_argument("--print-tree", action="store_true", help="Print interaction tree to stderr")
    p.add_argument("--dump-wire", action="store_true", help="Print interactions JSON")
    p.add_argument("--dump-wire-file", metavar="PATH", help="Write full wire JSON to file")
    p.add_argument("--flush-mode", default="validate", choices=("validate", "process", "ingest"))
    p.add_argument(
        "--sync",
        action="store_true",
        help="Invoke via sync Runner.run (still instrumented)",
    )
    args = p.parse_args()

    try:
        wire = run_once(
            mode=args.mode,
            local_only=True,
            flush_mode=args.flush_mode,
            use_sync=args.sync,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    assert_normalized_shape(wire)
    asserter = _TOPOLOGY_ASSERTERS.get(args.mode)
    if asserter:
        asserter(wire)

    if args.print_tree:
        try:
            from ollie.tree import render_interaction_tree

            print(render_interaction_tree(wire.get("interactions") or []), file=sys.stderr)
        except ImportError:
            print("ollie-sdk not installed; skipping --print-tree", file=sys.stderr)

    if args.dump_wire:
        print(json.dumps(wire.get("interactions") or [], indent=2))

    if args.dump_wire_file:
        Path(args.dump_wire_file).write_text(json.dumps(wire, indent=2) + "\n")
        print(f"wrote {args.dump_wire_file}", file=sys.stderr)

    if not args.dump_wire:
        print(json.dumps(wire, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
