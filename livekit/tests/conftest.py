from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "livekit: live LiveKit AgentSession e2e (OPENAI_API_KEY, network; excluded from default CI)",
    )


def _require_openai_key() -> str:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        pytest.skip("OPENAI_API_KEY required for live LiveKit e2e")
    return key


@pytest.fixture
def openai_api_key() -> str:
    return _require_openai_key()
