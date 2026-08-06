import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

pytest_plugins = ["integrations._test_support.conftest"]


@pytest.fixture
def e2e_tenant_purge():
    from integrations._test_support.e2e_ingest_helpers import e2e_customer_env
    from integrations._test_support.purge_trace_data import purge_trace_data

    os.environ.setdefault("E2E_INTEGRATION", "openai")
    cfg = e2e_customer_env("openai")
    yield cfg["customer_id"]
    try:
        purge_trace_data(cfg["customer_id"])
    except Exception:
        pass
