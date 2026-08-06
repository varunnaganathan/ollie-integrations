"""Hook idempotency tests for OpenAI Agents integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.instrumentation


def test_attach_ollie_idempotent():
    from ollie_integrations_openai_agents import hooks

    mock_client = MagicMock()
    hooks._patched = False
    hooks._orig.clear()
    hooks.attach_ollie(mock_client)
    orig_after_first = len(hooks._orig)
    hooks.attach_ollie(mock_client)
    assert hooks._patched is True
    assert len(hooks._orig) == orig_after_first


def test_attach_ollie_without_openai_agents_skips():
    from ollie_integrations_openai_agents import hooks

    mock_client = MagicMock()
    with patch.object(hooks, "_install_patches") as install:
        install.side_effect = lambda: None
        hooks.attach_ollie(mock_client)
