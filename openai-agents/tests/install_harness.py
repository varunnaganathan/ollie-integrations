"""Fresh venv helpers — re-exports shared install_harness (backward compatible)."""

from __future__ import annotations

import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parents[2] / "_test_support"
if str(_SHARED.parent.parent) not in sys.path:
    sys.path.insert(0, str(_SHARED.parent.parent))

from integrations._test_support.install_harness import (  # noqa: E402
    BACKEND_GIT,
    OPENAI_TAG,
    create_customer_venv,
    customer_install_openai_agents,
    destroy_customer_venv,
    installed_package_path,
    resolve_openai_agents_spec,
    resolve_ollie_sdk_spec,
    run_pip,
    run_python,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PACKAGE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_GIT_SPEC = (
    "ollie-integrations-openai-agents[agent] @ "
    f"git+{BACKEND_GIT}@{OPENAI_TAG}#subdirectory=integrations/openai-agents"
)


def resolve_integration_spec() -> str:
    return resolve_openai_agents_spec()


def customer_install_sequence(env: dict) -> None:
    customer_install_openai_agents(env)


__all__ = [
    "_PACKAGE_DIR",
    "_REPO_ROOT",
    "create_customer_venv",
    "customer_install_sequence",
    "destroy_customer_venv",
    "installed_package_path",
    "resolve_integration_spec",
    "resolve_ollie_sdk_spec",
    "run_pip",
    "run_python",
]
