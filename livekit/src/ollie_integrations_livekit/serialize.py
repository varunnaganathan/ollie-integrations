"""Serialization helpers for LiveKit wire payloads."""

from __future__ import annotations

import json
from typing import Any

_MAX_CHARS = 32_000


def truncate(s: str | None) -> tuple[str, bool]:
    if s is None:
        return "", False
    text = str(s)
    if len(text) <= _MAX_CHARS:
        return text, False
    return text[:_MAX_CHARS] + "…", True


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:
        return str(obj)


def session_start_input(*, room: str | None = None, participant: str | None = None) -> str:
    parts = ["session_start"]
    if room:
        parts.append(f"room={room}")
    if participant:
        parts.append(f"participant={participant}")
    return " ".join(parts)


def audio_ref(label: str = "audio_stream") -> str:
    return f"[{label}]"


def transcript_text(text: str | None) -> str:
    return str(text or "").strip()
