"""Hook LiveKit AgentSession and emit Ollie v2 execution trees."""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

from ollie_integrations_livekit.collector import ExecutionSpanCollector
from ollie_integrations_livekit.emit import collector_to_wire_payload, flush_collector_to_client
from ollie_integrations_livekit.serialize import audio_ref, safe_json, session_start_input, transcript_text

logger = logging.getLogger(__name__)

_client: Any | None = None
_app_name: str = "livekit_session"
_flush_mode: str = "ingest"
_patched: bool = False
_last_wire_payload: dict[str, Any] | None = None
_orig: dict[str, Any] = {}


def get_last_wire_payload() -> dict[str, Any] | None:
    """Return the most recently emitted v2 payload (after session close)."""
    return _last_wire_payload


def _capture_content_enabled() -> bool:
    val = os.getenv("LIVEKIT_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def attach_ollie(
    client: Any,
    *,
    app_name: str | None = None,
    flush_mode: str = "ingest",
    session: Any | None = None,
) -> None:
    """Install LiveKit hooks that emit Ollie v2 payloads after each AgentSession."""
    global _client, _app_name, _flush_mode
    _client = client
    _app_name = (app_name or os.getenv("OLLIE_LIVEKIT_APP_NAME") or "livekit_session").strip()
    _flush_mode = str(flush_mode or "ingest").strip().lower()
    _install_patches()
    if session is not None:
        _register_session_handlers(session)


def _install_patches() -> None:
    global _patched
    if _patched:
        return
    try:
        from livekit.agents.voice import AgentSession
    except ImportError:
        logger.warning(
            "livekit-agents not installed; attach_ollie registered client only. "
            "Install with: pip install ollie-integrations-livekit[agent]"
        )
        return

    if "AgentSession.start" not in _orig:
        _orig["AgentSession.start"] = AgentSession.start
        AgentSession.start = _wrap_session_start(_orig["AgentSession.start"])  # type: ignore[method-assign]

    _patched = True


def _wrap_session_start(orig):
    @functools.wraps(orig)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        room = kwargs.get("room")
        if room is None and args:
            room = args[0]
        room_name = getattr(room, "name", None) if room is not None else None
        job_id = getattr(getattr(self, "_job_context", None), "job_id", None)

        collector = ExecutionSpanCollector(
            app_name=_app_name,
            session_id=str(getattr(room, "sid", None) or room_name or _app_name),
            capture_content=_capture_content_enabled(),
            room=str(room_name) if room_name else None,
            job_id=str(job_id) if job_id else None,
        )
        ExecutionSpanCollector.set_current(collector)
        session_id = collector.open_agent_session(
            input_text=session_start_input(room=str(room_name) if room_name else None)
        )
        _register_session_handlers(self, collector=collector, session_node_id=session_id)

        capture_run = bool(kwargs.get("capture_run", False))
        try:
            result = await orig(self, *args, **kwargs)
            return result
        except Exception:
            collector.status = "failed"
            collector.close_agent_session(session_id, output_text="session_failed", success=False)
            raise
        finally:
            started = bool(getattr(self, "_started", False))
            # capture_run=True: the turn completes inside start(); otherwise flush on session close.
            if not started or capture_run:
                if session_id in collector._nodes and not collector._nodes[session_id].closed:
                    collector.close_agent_session(session_id, output_text="session_ended", success=True)
                ExecutionSpanCollector.set_current(None)
                _flush_collector(collector)

    return wrapper


def _flush_collector(collector: ExecutionSpanCollector) -> None:
    global _last_wire_payload
    if getattr(collector, "_ollie_flushed", False):
        return
    if _client is None or not collector.nodes_in_order():
        return
    collector._ollie_flushed = True
    try:
        _last_wire_payload = collector_to_wire_payload(
            collector, agent_id=_client.agent_id, session_id=collector.session_id
        )
        flush_collector_to_client(collector, _client, flush_mode=_flush_mode)
    except Exception as exc:
        logger.exception("Ollie LiveKit flush failed: %s", exc)


def _register_session_handlers(
    session: Any,
    *,
    collector: ExecutionSpanCollector | None = None,
    session_node_id: str | None = None,
) -> None:
    if collector is None:
        collector = ExecutionSpanCollector.current()
    if collector is None:
        return

    state: dict[str, Any] = {
        "collector": collector,
        "session_node_id": session_node_id,
        "turn_id": None,
        "stt_id": None,
        "turn_detection_id": None,
        "agent_id": None,
        "tts_id": None,
        "agent_name": "voice_agent",
        "partial_transcript": "",
    }

    def _ensure_turn() -> str:
        if state["turn_id"] and state["turn_id"] in collector._nodes:
            node = collector._nodes[state["turn_id"]]
            if not node.closed:
                return state["turn_id"]
        tid = collector.open_user_turn(input_text=audio_ref("user_audio"))
        state["turn_id"] = tid
        return tid

    def _on_user_input_transcribed(ev: Any) -> None:
        transcript = transcript_text(getattr(ev, "transcript", None))
        is_final = bool(getattr(ev, "is_final", False))
        _ensure_turn()
        if state["stt_id"] is None or (
            state["stt_id"] in collector._nodes and collector._nodes[state["stt_id"]].closed
        ):
            state["stt_id"] = collector.open_stt(input_text=audio_ref("user_audio"))
        stt_id = state["stt_id"]
        if is_final:
            collector.add_event(stt_id, "livekit.final_transcript", payload={"text": transcript})
            collector.close_stt(stt_id, output_text=transcript, success=True)
            state["partial_transcript"] = transcript
            state["stt_id"] = None
        else:
            collector.add_event(stt_id, "livekit.partial_transcript", payload={"text": transcript})
            state["partial_transcript"] = transcript

    def _on_user_state_changed(ev: Any) -> None:
        new_state = str(getattr(ev, "new_state", "") or "")
        if new_state == "speaking":
            _ensure_turn()
            if state["stt_id"] is None:
                state["stt_id"] = collector.open_stt(input_text=audio_ref("user_audio"))

    def _on_agent_state_changed(ev: Any) -> None:
        new_state = str(getattr(ev, "new_state", "") or "")
        old_state = str(getattr(ev, "old_state", "") or "")
        if new_state == "thinking" and state["agent_id"] is None:
            _ensure_turn()
            if state["turn_detection_id"] is None or (
                state["turn_detection_id"] in collector._nodes
                and collector._nodes[state["turn_detection_id"]].closed
            ):
                state["turn_detection_id"] = collector.open_turn_detection(
                    input_text=state["partial_transcript"] or transcript_text("")
                )
                collector.add_event(state["turn_detection_id"], "livekit.semantic_complete")
                collector.close_turn_detection(
                    state["turn_detection_id"],
                    output_text="turn_complete",
                    success=True,
                )
                state["turn_detection_id"] = None
            agent = getattr(session, "current_agent", None) or getattr(session, "_agent", None)
            agent_name = getattr(agent, "name", None) or state["agent_name"]
            state["agent_id"] = collector.open_agent(
                str(agent_name),
                input_text=state["partial_transcript"] or "",
            )
            collector.add_event(state["agent_id"], "livekit.llm_start")
        elif old_state == "thinking" and new_state != "thinking" and state["agent_id"]:
            collector.add_event(state["agent_id"], "livekit.llm_end")
        elif new_state == "speaking" and state["tts_id"] is None:
            _ensure_turn()
            state["tts_id"] = collector.open_tts(input_text="")

    def _on_speech_created(ev: Any) -> None:
        _ensure_turn()
        if state["tts_id"] is None:
            source = str(getattr(ev, "source", "") or "")
            state["tts_id"] = collector.open_tts(input_text=source or "response_text")

    def _on_function_tools_executed(ev: Any) -> None:
        _ensure_turn()
        if state["agent_id"] is None:
            state["agent_id"] = collector.open_agent(state["agent_name"], input_text="")
        tool_calls = getattr(ev, "function_calls", None) or getattr(ev, "tools", None) or []
        results = getattr(ev, "function_call_outputs", None) or getattr(ev, "results", None) or []
        if not isinstance(tool_calls, list):
            tool_calls = [tool_calls]
        if not isinstance(results, list):
            results = [results]
        for i, call in enumerate(tool_calls):
            name = getattr(call, "name", None) or getattr(call, "tool_name", None) or "tool"
            args = getattr(call, "arguments", None) or getattr(call, "args", None) or {}
            result = results[i] if i < len(results) else {}
            collector.add_event(state["agent_id"], "livekit.tool_request", payload={"tool": name})
            tool_id = collector.open_tool(str(name), input_text=safe_json(args))
            out = getattr(result, "output", None) or getattr(result, "result", None) or result
            collector.close_tool(tool_id, output_text=safe_json(out), success=True)

    def _on_conversation_item_added(ev: Any) -> None:
        item = getattr(ev, "item", None)
        if item is None:
            return
        role = str(getattr(item, "role", "") or "")
        text = ""
        content = getattr(item, "content", None)
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(str(c) for c in content)
        if role in ("assistant", "agent") and state["agent_id"]:
            node = collector._nodes.get(state["agent_id"])
            if node and not node.closed:
                node.output_text = text
        if role in ("assistant", "agent") and state["tts_id"]:
            node = collector._nodes.get(state["tts_id"])
            if node and not node.closed:
                node.input_text = text
            collector.close_tts(state["tts_id"], output_text=audio_ref("agent_audio"), success=True)
            state["tts_id"] = None
            if state["agent_id"] and not collector._nodes[state["agent_id"]].closed:
                collector.close_agent(state["agent_id"], output_text=text, success=True)
                state["agent_id"] = None
            if state["turn_id"] and not collector._nodes[state["turn_id"]].closed:
                collector.close_user_turn(state["turn_id"], output_text=audio_ref("agent_audio"), success=True)
                state["turn_id"] = None

    def _on_agent_false_interruption(ev: Any) -> None:
        td_id = collector.open_turn_detection(input_text=state["partial_transcript"] or "")
        collector.add_event(td_id, "livekit.interruption")
        collector.close_turn_detection(td_id, output_text="interrupt", success=True, interrupted=True)

    def _on_user_turn_exceeded(ev: Any) -> None:
        td_id = collector.open_turn_detection(input_text=state["partial_transcript"] or "")
        collector.add_event(td_id, "livekit.turn_exceeded")
        collector.close_turn_detection(td_id, output_text="continue_listening", success=False)

    def _on_close(ev: Any) -> None:
        for key, closer in (
            ("agent_id", lambda nid: collector.close_agent(nid, success=True)),
            ("tts_id", lambda nid: collector.close_tts(nid, success=True)),
            ("stt_id", lambda nid: collector.close_stt(nid, success=True)),
            ("turn_detection_id", lambda nid: collector.close_turn_detection(nid, success=True)),
            ("turn_id", lambda nid: collector.close_user_turn(nid, success=True)),
        ):
            nid = state.get(key)
            if nid and nid in collector._nodes and not collector._nodes[nid].closed:
                closer(nid)
        sid = state.get("session_node_id")
        if sid and sid in collector._nodes and not collector._nodes[sid].closed:
            collector.close_agent_session(sid, output_text="session_ended", success=True)
        ExecutionSpanCollector.set_current(None)
        _flush_collector(collector)

    handlers = {
        "user_input_transcribed": _on_user_input_transcribed,
        "user_state_changed": _on_user_state_changed,
        "agent_state_changed": _on_agent_state_changed,
        "speech_created": _on_speech_created,
        "function_tools_executed": _on_function_tools_executed,
        "conversation_item_added": _on_conversation_item_added,
        "agent_false_interruption": _on_agent_false_interruption,
        "user_turn_exceeded": _on_user_turn_exceeded,
        "close": _on_close,
    }
    for event_name, handler in handlers.items():
        try:
            session.on(event_name, handler)
        except Exception as exc:
            logger.debug("LiveKit hook: could not register %s: %s", event_name, exc)
