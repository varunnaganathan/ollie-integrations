import json
from pathlib import Path

import pytest

from e2e.validators import assert_interaction_tree, assert_live_hook_tree
from helpers import build_single_turn_voice_tree
from ollie_integrations_livekit.emit import collector_to_wire_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_sample_tree_from_collector():
    wire = collector_to_wire_payload(
        build_single_turn_voice_tree(),
        agent_id="agent_test",
        session_id="sess-voice-001",
    )
    assert_interaction_tree(wire)


def test_golden_fixture_validates():
    wire = json.loads((FIXTURES / "single_turn_voice_pipeline.json").read_text())
    assert_interaction_tree(wire)


def test_synthetic_run_once_smoke():
    from examples.sample_livekit_agent.run import run_once_synthetic

    wire = run_once_synthetic(local_only=True)
    assert_interaction_tree(wire)


@pytest.mark.livekit
@pytest.mark.e2e
@pytest.mark.openai
@pytest.mark.asyncio
async def test_live_livekit_agent_tree(openai_api_key):
    pytest.importorskip("livekit.plugins.openai")
    from examples.sample_livekit_agent.run import run_once_live

    wire = await run_once_live(flush_mode="validate", timeout_s=90)
    assert_live_hook_tree(wire, text_mode=True)
