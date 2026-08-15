"""Hook OpenAI Agents Runner.run and emit Ollie traces."""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

from ollie_integrations_openai_agents.collector import RunCollector
from ollie_integrations_openai_agents.emit import flush_collector_to_client
from ollie_integrations_openai_agents.processor import register_processor
from ollie_integrations_openai_agents.serialize import to_input_str

logger = logging.getLogger(__name__)

_client: Any | None = None
_workflow_name: str = "openai_agents_run"
_flush_mode: str = "ingest"
_patched: bool = False
_processor_registered: bool = False
_last_wire_payload: dict[str, Any] | None = None
_orig: dict[str, Any] = {}


def get_last_wire_payload() -> dict[str, Any] | None:
    return _last_wire_payload


def attach_ollie(
    client: Any,
    *,
    workflow_name: str | None = None,
    flush_mode: str = "ingest",
) -> None:
    global _client, _workflow_name, _flush_mode, _processor_registered
    _client = client
    _workflow_name = (workflow_name or "openai_agents_run").strip()
    _flush_mode = str(flush_mode or "ingest").strip().lower()
    if not _processor_registered:
        try:
            register_processor()
            _processor_registered = True
        except ImportError:
            logger.warning("openai-agents not installed; span collection disabled until package is available")
    _install_patches()


def _install_patches() -> None:
    global _patched
    if _patched:
        return
    try:
        from agents.run import Runner
    except ImportError:
        logger.warning("openai-agents not installed; attach_ollie registered client only")
        _patched = True
        return

    if "Runner.run" not in _orig:
        raw_run = Runner.__dict__["run"]
        _orig["Runner.run"] = raw_run.__func__ if isinstance(raw_run, classmethod) else raw_run
        Runner.run = classmethod(_wrap_run_async(_orig["Runner.run"]))  # type: ignore[method-assign]
    if "Runner.run_sync" not in _orig:
        raw_sync = Runner.__dict__["run_sync"]
        _orig["Runner.run_sync"] = (
            raw_sync.__func__ if isinstance(raw_sync, classmethod) else raw_sync
        )
        Runner.run_sync = classmethod(_wrap_run_sync(_orig["Runner.run_sync"]))  # type: ignore[method-assign]
    _patched = True


_RUNNER_STRIP_KEYS = frozenset({"session_id"})


def _collector_session_id(kwargs: dict[str, Any]) -> str | None:
    env = (os.environ.get("OLLIE_SESSION_ID") or "").strip()
    if env:
        return env
    for key in ("conversation_id", "session_id"):
        val = kwargs.get(key)
        if val:
            return str(val)
    return None


def _runner_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if k not in _RUNNER_STRIP_KEYS}


def _wrap_run_async(orig):
    @functools.wraps(orig)
    async def wrapper(cls, starting_agent, input, **kwargs):
        runner_kwargs = _runner_kwargs(kwargs)
        return await _run_with_collector(
            lambda: orig(cls, starting_agent, input, **runner_kwargs),
            agent=starting_agent,
            input_value=input,
            kwargs=kwargs,
        )

    return wrapper


def _wrap_run_sync(orig):
    @functools.wraps(orig)
    def wrapper(cls, starting_agent, input, **kwargs):
        return _run_sync_with_collector(orig, cls, starting_agent, input, kwargs)

    return wrapper


def _run_sync_with_collector(orig, cls, starting_agent, input_value, kwargs):
    global _last_wire_payload
    runner_kwargs = _runner_kwargs(kwargs)
    if _client is None:
        return orig(cls, starting_agent, input_value, **runner_kwargs)

    name = _workflow_name
    if hasattr(starting_agent, "name") and starting_agent.name:
        name = str(starting_agent.name)

    collector = RunCollector(
        workflow_name=name,
        session_id=_collector_session_id(kwargs),
        input_text=to_input_str(input_value),
    )
    RunCollector.set_current(collector)
    try:
        result = orig(cls, starting_agent, input_value, **runner_kwargs)
        out = str(getattr(result, "final_output", None) or getattr(result, "finalOutput", "") or "")
        collector.close(output=out, success=True)
        return result
    except Exception:
        collector.close(output="", success=False)
        raise
    finally:
        RunCollector.set_current(None)
        try:
            from ollie_integrations_openai_agents.emit import collector_to_wire_payload

            _last_wire_payload = collector_to_wire_payload(
                collector,
                agent_id=_client.agent_id,
                session_id=collector.session_id,
            )
            flush_collector_to_client(collector, _client, flush_mode=_flush_mode)
        except Exception:
            logger.exception("ollie openai-agents flush failed")


async def _run_with_collector(coro_factory, *, agent, input_value, kwargs):
    global _last_wire_payload
    if _client is None:
        return await coro_factory()

    name = _workflow_name
    if hasattr(agent, "name") and agent.name:
        name = str(agent.name)

    collector = RunCollector(
        workflow_name=name,
        session_id=_collector_session_id(kwargs),
        input_text=to_input_str(input_value),
    )
    RunCollector.set_current(collector)
    success = True
    result = None
    try:
        result = await coro_factory()
        out = ""
        if result is not None:
            out = str(getattr(result, "final_output", None) or getattr(result, "finalOutput", "") or "")
        collector.close(output=out, success=True)
        return result
    except Exception:
        success = False
        collector.close(output="", success=False)
        raise
    finally:
        RunCollector.set_current(None)
        try:
            from ollie_integrations_openai_agents.emit import collector_to_wire_payload

            _last_wire_payload = collector_to_wire_payload(
                collector,
                agent_id=_client.agent_id,
                session_id=collector.session_id,
            )
            flush_collector_to_client(collector, _client, flush_mode=_flush_mode)
        except Exception:
            logger.exception("ollie openai-agents flush failed")
        if not success:
            pass
