"""Hook Google ADK runtime and emit Ollie v2 execution trees."""

from __future__ import annotations

import contextlib
import functools
import logging
import os
from typing import Any, AsyncIterator, Generator

from ollie_integrations_google_adk.collector import ExecutionSpanCollector
from ollie_integrations_google_adk.emit import flush_collector_to_client
from ollie_integrations_google_adk.serialize import (
    content_to_input_string,
    final_model_text,
    llm_request_input,
    llm_response_output,
    safe_json,
    session_messages_for_invocation,
)

logger = logging.getLogger(__name__)

_client: Any | None = None
_app_name: str = "adk_workflow"
_flush_mode: str = "ingest"
_patched: bool = False
_last_wire_payload: dict[str, Any] | None = None

_orig: dict[str, Any] = {}

SAFETY_FINISH = frozenset({"safety", "content_filter", "content_filtered"})


def get_last_wire_payload() -> dict[str, Any] | None:
    """Return the most recently emitted v2 payload (after run / run_async completes)."""
    return _last_wire_payload


def _capture_content_enabled() -> bool:
    val = os.getenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def attach_ollie(
    client: Any,
    *,
    app_name: str | None = None,
    flush_mode: str = "ingest",
    runner: Any | None = None,
) -> None:
    """Install ADK hooks that emit Ollie v2 payloads after each Runner.run / run_async."""
    global _client, _app_name, _flush_mode, _patched
    _client = client
    _app_name = (app_name or os.getenv("OLLIE_ADK_APP_NAME") or "adk_workflow").strip()
    _flush_mode = str(flush_mode or "ingest").strip().lower()
    _install_patches()
    if runner is not None:
        logger.debug("attach_ollie: runner=%s app_name=%s", type(runner).__name__, _app_name)


def _install_patches() -> None:
    global _patched
    if _patched:
        return
    try:
        import google.adk.runners as runners_mod
        import google.adk.telemetry._instrumentation as instr_mod
        import google.adk.telemetry.tracing as tracing_mod
    except ImportError:
        logger.warning(
            "google-adk not installed; attach_ollie registered client only. "
            "Install with: pip install ollie-integrations-google-adk[agent]"
        )
        _patched = True
        return

    if "Runner.run_async" not in _orig:
        _orig["Runner.run_async"] = runners_mod.Runner.run_async
        runners_mod.Runner.run_async = _wrap_run_async(_orig["Runner.run_async"])  # type: ignore[method-assign]

    if "Runner.run" not in _orig:
        _orig["Runner.run"] = runners_mod.Runner.run
        runners_mod.Runner.run = _wrap_run_sync(_orig["Runner.run"])  # type: ignore[method-assign]

    if "record_agent_invocation" not in _orig:
        _orig["record_agent_invocation"] = instr_mod.record_agent_invocation
        instr_mod.record_agent_invocation = _wrap_record_agent_invocation(
            _orig["record_agent_invocation"]
        )

    if "record_tool_execution" not in _orig:
        _orig["record_tool_execution"] = instr_mod.record_tool_execution
        instr_mod.record_tool_execution = _wrap_record_tool_execution(_orig["record_tool_execution"])

    if "trace_call_llm" not in _orig:
        _orig["trace_call_llm"] = tracing_mod.trace_call_llm
        tracing_mod.trace_call_llm = _wrap_trace_call_llm(_orig["trace_call_llm"])

    _patched = True


def _wrap_run_sync(orig):
    """Thin wrapper: ADK sync run() already delegates to run_async (which we instrument)."""

    @functools.wraps(orig)
    def wrapper(self, *args: Any, **kwargs: Any) -> Generator[Any, None, None]:
        yield from orig(self, *args, **kwargs)

    return wrapper


def _wrap_run_async(orig):
    @functools.wraps(orig)
    async def wrapper(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        new_message = kwargs.get("new_message")
        if new_message is None and len(args) >= 3:
            new_message = args[2]
        session_id = kwargs.get("session_id")
        if session_id is None and len(args) >= 2:
            session_id = args[1]

        app = _app_name or getattr(self, "app_name", None) or "adk_workflow"
        collector = ExecutionSpanCollector(
            app_name=str(app),
            session_id=str(session_id) if session_id else None,
            capture_content=_capture_content_enabled(),
        )
        ExecutionSpanCollector.set_current(collector)
        wf_id: str | None = None
        inp = content_to_input_string(new_message)
        wf_id = collector.open_workflow(input_text=inp)

        try:
            async for event in orig(self, *args, **kwargs):
                yield event
        except Exception:
            collector.status = "failed"
            if wf_id:
                collector.close_node(wf_id, output_text="", success=False)
            raise
        else:
            if wf_id:
                out = None
                if collector.invocation_id:
                    try:
                        user_id = kwargs.get("user_id") or (args[0] if args else None)
                        sid = session_id or kwargs.get("session_id")
                        if user_id and sid:
                            session = await self._get_or_create_session(
                                user_id=user_id, session_id=sid
                            )
                            out = final_model_text(session, collector.invocation_id)
                    except Exception as exc:
                        logger.debug("workflow output resolution skipped: %s", exc)
                collector.close_node(wf_id, output_text=out or "", success=True)
        finally:
            ExecutionSpanCollector.set_current(None)
            if _client is not None and collector.nodes_in_order():
                try:
                    from ollie_integrations_google_adk.emit import collector_to_wire_payload

                    global _last_wire_payload
                    _last_wire_payload = collector_to_wire_payload(
                        collector,
                        agent_id=_client.agent_id,
                        session_id=collector.session_id,
                    )
                    flush_collector_to_client(
                        collector,
                        _client,
                        flush_mode=_flush_mode,
                    )
                except Exception as exc:
                    logger.exception("Ollie ADK flush failed: %s", exc)

    return wrapper


def _wrap_record_tool_execution(orig):
    @contextlib.asynccontextmanager
    @functools.wraps(orig)
    async def wrapper(tool, agent, function_args, *args: Any, **kwargs: Any):
        collector = ExecutionSpanCollector.current()
        tool_id: str | None = None
        if collector is not None:
            tool_id = collector.open_tool(tool.name, input_text=safe_json(function_args or {}))
        caught: Exception | None = None
        tel_ctx = None
        try:
            async with orig(tool, agent, function_args, *args, **kwargs) as tel_ctx:
                yield tel_ctx
        except Exception as exc:
            caught = exc
            raise
        finally:
            if collector is not None and tool_id:
                success = caught is None and (tel_ctx is None or getattr(tel_ctx, "error_type", None) is None)
                err_type = getattr(tel_ctx, "error_type", None) if tel_ctx else None
                if caught is not None:
                    err_type = type(caught).__name__
                output = ""
                ev = getattr(tel_ctx, "function_response_event", None) if tel_ctx else None
                if ev is not None and collector.capture_content:
                    content = getattr(ev, "content", None)
                    if content is not None:
                        parts = getattr(content, "parts", None) or []
                        for part in parts:
                            fr = getattr(part, "function_response", None)
                            if fr is not None:
                                resp = getattr(fr, "response", None)
                                output = safe_json(resp if resp is not None else {})
                                break
                if caught is not None:
                    output = safe_json({"error": str(caught)})
                    success = False
                collector.close_tool(
                    tool_id,
                    output_text=output,
                    success=success,
                    error_type=str(err_type) if err_type else None,
                )

    return wrapper


def _wrap_record_agent_invocation(orig):
    @contextlib.asynccontextmanager
    @functools.wraps(orig)
    async def wrapper(ctx, agent, *args: Any, **kwargs: Any):
        collector = ExecutionSpanCollector.current()
        agent_node_id: str | None = None
        if collector is not None:
            collector.invocation_id = getattr(ctx, "invocation_id", None)
            if getattr(ctx, "session", None) is not None:
                collector.session_id = getattr(ctx.session, "id", None) or collector.session_id
            branch = getattr(ctx, "branch", None)
            branch_s = str(branch).strip() if branch is not None and str(branch).strip() else None
            is_delegation = bool(branch_s)
            inp = session_messages_for_invocation(
                ctx.session,
                str(ctx.invocation_id),
                branch=branch_s,
                author=agent.name,
            )
            agent_node_id = collector.open_agent(
                agent.name,
                input_text=inp,
                is_delegation=is_delegation,
                agent_branch=branch_s,
                author=agent.name,
            )
        try:
            async with orig(ctx, agent, *args, **kwargs) as tel_ctx:
                yield tel_ctx
        finally:
            if collector is not None and agent_node_id:
                out = final_model_text(ctx.session, str(ctx.invocation_id), author=agent.name)
                collector.close_agent(agent_node_id, output_text=out or "", success=True)

    return wrapper


def _wrap_trace_call_llm(orig):
    @functools.wraps(orig)
    def wrapper(invocation_context, event_id, llm_request, llm_response, span=None, *args: Any, **kwargs: Any):
        collector = ExecutionSpanCollector.current()
        llm_id: str | None = None
        if collector is not None and getattr(invocation_context, "agent", None) is not None:
            agent_name = invocation_context.agent.name
            model = getattr(llm_request, "model", None)
            llm_name = str(model) if model else f"{agent_name}.llm"
            inp = llm_request_input(llm_request) if collector.capture_content else ""
            llm_id = collector.open_llm(llm_name, input_text=inp)
        try:
            # Prefer kwargs-forwarding for ADK signature drift; fall back to known arity.
            try:
                orig(
                    invocation_context,
                    event_id,
                    llm_request,
                    llm_response,
                    span=span,
                    *args,
                    **kwargs,
                )
            except TypeError:
                orig(invocation_context, event_id, llm_request, llm_response, span=span)
        except Exception as exc:
            if collector is not None and llm_id:
                collector.close_llm(
                    llm_id,
                    output_text="",
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            raise
        if collector is not None and llm_id:
            out = llm_response_output(llm_response) if collector.capture_content else ""
            usage = _usage_token_parts(llm_response)
            finish = _finish_reason(llm_response)
            error_code = _error_code(llm_response)
            error_type = _error_type(llm_response)
            error_message = _error_message(llm_response)
            success = _llm_success(finish, error_code) and not bool(error_message)
            collector.close_llm(
                llm_id,
                output_text=out,
                success=success,
                token_count=usage.get("token_count"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                cached_tokens=usage.get("cached_tokens"),
                thoughts_tokens=usage.get("thoughts_tokens"),
                finish_reason=finish,
                error_code=error_code,
                error_type=error_type,
                error_message=error_message,
            )

    return wrapper


def _llm_success(finish_reason: str | None, error_code: str | None = None) -> bool:
    from ollie_integrations_google_adk.signals.direct import (
        MALFORMED_FINISH,
        RATE_LIMIT_CODES,
        SAFETY_FINISH,
        UNAVAILABLE_CODES,
    )

    if error_code and str(error_code).strip().lower() in (RATE_LIMIT_CODES | UNAVAILABLE_CODES):
        return False
    if not finish_reason:
        return True
    fr = finish_reason.lower()
    return fr not in (SAFETY_FINISH | MALFORMED_FINISH)


def _usage_token_parts(llm_response: Any) -> dict[str, int | None]:
    usage = getattr(llm_response, "usage_metadata", None)
    if usage is None:
        return {
            "token_count": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "cached_tokens": None,
            "thoughts_tokens": None,
        }
    prompt = getattr(usage, "prompt_token_count", None)
    if prompt is None:
        prompt = getattr(usage, "input_tokens", None)
    completion = getattr(usage, "candidates_token_count", None)
    if completion is None:
        completion = getattr(usage, "output_tokens", None)
    cached = getattr(usage, "cached_content_token_count", None)
    if cached is None:
        cached = getattr(usage, "cached_tokens", None)
    thoughts = getattr(usage, "thoughts_token_count", None)
    if thoughts is None:
        thoughts = getattr(usage, "thoughts_tokens", None)

    def _as_int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    prompt_i = _as_int(prompt)
    completion_i = _as_int(completion)
    cached_i = _as_int(cached)
    thoughts_i = _as_int(thoughts)
    total = None
    if prompt_i is not None or completion_i is not None:
        total = int(prompt_i or 0) + int(completion_i or 0)
    return {
        "token_count": total,
        "prompt_tokens": prompt_i,
        "completion_tokens": completion_i,
        "cached_tokens": cached_i,
        "thoughts_tokens": thoughts_i,
    }


def _usage_tokens(llm_response: Any) -> int | None:
    """Back-compat helper: summed prompt + completion tokens."""
    return _usage_token_parts(llm_response).get("token_count")


def _finish_reason(llm_response: Any) -> str | None:
    fr = getattr(llm_response, "finish_reason", None)
    if fr is None:
        return None
    if hasattr(fr, "value"):
        return str(fr.value).lower()
    return str(fr).lower()


def _error_code(llm_response: Any) -> str | None:
    for attr in ("error_code", "code", "status_code"):
        val = getattr(llm_response, attr, None)
        if val is not None and str(val).strip():
            return str(val).strip().lower()
    err = getattr(llm_response, "error", None)
    if err is None:
        return None
    if isinstance(err, dict):
        for key in ("code", "error_code", "status", "status_code"):
            if err.get(key) is not None and str(err.get(key)).strip():
                return str(err.get(key)).strip().lower()
        return None
    for attr in ("code", "error_code", "status_code"):
        val = getattr(err, attr, None)
        if val is not None and str(val).strip():
            return str(val).strip().lower()
    return None


def _error_type(llm_response: Any) -> str | None:
    for attr in ("error_type", "error_name"):
        val = getattr(llm_response, attr, None)
        if val is not None and str(val).strip():
            return str(val).strip()
    err = getattr(llm_response, "error", None)
    if err is None:
        return None
    if isinstance(err, dict):
        t = err.get("type") or err.get("error_type")
        return str(t).strip() if t else None
    name = type(err).__name__ if not isinstance(err, str) else None
    return name


def _error_message(llm_response: Any) -> str | None:
    for attr in ("error_message", "llm_error_message", "message"):
        val = getattr(llm_response, attr, None)
        if val is not None and str(val).strip() and attr != "message":
            return str(val).strip()
    err = getattr(llm_response, "error", None)
    if err is None:
        return None
    if isinstance(err, str) and err.strip():
        return err.strip()
    if isinstance(err, dict):
        for key in ("message", "error_message", "msg", "detail"):
            if err.get(key) is not None and str(err.get(key)).strip():
                return str(err.get(key)).strip()
        return None
    msg = getattr(err, "message", None)
    if msg is not None and str(msg).strip():
        return str(msg).strip()
    text = str(err).strip()
    return text or None
