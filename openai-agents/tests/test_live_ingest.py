"""E2E ingest tests for OpenAI Agents (synthetic wire)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from openai_helpers import build_single_tool_run  # noqa: E402
from ollie_integrations_openai_agents.emit import collector_to_wire_payload  # noqa: E402
from ollie_integrations_openai_agents.hooks import flush_collector_to_client  # noqa: E402

pytestmark = pytest.mark.e2e_ingest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from integrations._test_support.e2e_ingest_helpers import (  # noqa: E402
    assert_trace_interactions,
    database_configured,
    ingest_configured,
    ingest_stack_available,
    make_ollie_client,
    unique_session_id,
    wait_for_trace_in_db,
)


@pytest.fixture
def require_e2e_stack():
    if not ingest_configured():
        pytest.skip("OLLIE_API_KEY and OLLIE_AGENT_ID required")
    if not database_configured():
        pytest.skip("DATABASE_URL required")
    if not ingest_stack_available():
        pytest.skip("ingest stack not reachable")


def test_e2e_synthetic_openai_ingest(require_e2e_stack, e2e_tenant_purge):
    customer_id = os.getenv("OPENAI_E2E_CUSTOMER_ID", "cust_openai_e2e_1")
    session_id = unique_session_id("openai-e2e")
    collector = build_single_tool_run()
    collector.session_id = session_id
    wire = collector_to_wire_payload(collector, agent_id=os.getenv("OLLIE_AGENT_ID", "agent_openai_e2e_1"))
    client = make_ollie_client()
    flush_collector_to_client(collector, client, flush_mode="ingest")
    assert wait_for_trace_in_db(session_id, customer_id=customer_id)
    assert_trace_interactions(
        session_id,
        1,
        customer_id=customer_id,
        expect_signal="used_tool",
        expect_min_spans=1,
    )


@pytest.mark.openai
def test_e2e_live_sample_openai_agent_ingest(require_e2e_stack, e2e_tenant_purge):
    """Live OpenAI Agents sample → attach_ollie ingest → Postgres."""
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        pytest.skip("OPENAI_API_KEY required for live sample agent")
    pytest.importorskip("agents")

    import asyncio
    import sys
    from pathlib import Path

    examples = Path(__file__).resolve().parents[1] / "examples"
    if str(examples) not in sys.path:
        sys.path.insert(0, str(examples))

    from sample_openai_agent.run import run_once

    customer_id = os.getenv("OPENAI_E2E_CUSTOMER_ID", "cust_openai_e2e_1")
    client = make_ollie_client()
    wire = asyncio.run(
        run_once(
            "single_agent_tool",
            flush_mode="ingest",
            use_mock_client=False,
            client=client,
        )
    )
    session_id = str(wire.get("session_id") or "")
    assert session_id
    assert wait_for_trace_in_db(session_id, customer_id=customer_id, timeout=90), (
        f"trace {session_id} not in DB"
    )
    assert_trace_interactions(session_id, 1, customer_id=customer_id, expect_min_spans=1)
