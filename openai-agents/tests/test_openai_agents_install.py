"""Customer install tests per install-before-pypi.md (fresh temp venv)."""

from __future__ import annotations

import os

import pytest

from install_harness import (
    _PACKAGE_DIR,
    customer_install_sequence,
    installed_package_path,
    run_python,
)

pytestmark = pytest.mark.install


def test_customer_install_sequence(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)


def test_verify_imports_from_doc(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)
    result = run_python(
        openai_agents_install_env,
        "from ollie_integrations_openai_agents import attach_ollie; print('ok')",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_version_matches_release(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)
    result = run_python(
        openai_agents_install_env,
        "import ollie_integrations_openai_agents as m; print(m.__version__)",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0"


def test_public_api_exports(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)
    result = run_python(
        openai_agents_install_env,
        (
            "from ollie_integrations_openai_agents import ("
            "attach_ollie, normalize_collector, collector_to_wire_payload, get_last_wire_payload"
            "); print('ok')"
        ),
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_agent_extra_openai_agents_importable(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)
    result = run_python(openai_agents_install_env, "import agents; print('ok')")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_attach_ollie_no_raise_after_install(openai_agents_install_env):
    customer_install_sequence(openai_agents_install_env)
    script = """
from unittest.mock import MagicMock
from ollie_integrations_openai_agents import attach_ollie
client = MagicMock()
client.agent_id = "agent_install_test"
attach_ollie(client, workflow_name="install_test", flush_mode="validate")
print("ok")
"""
    result = run_python(openai_agents_install_env, script)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_no_monorepo_packages_on_path(openai_agents_install_env):
    if (os.getenv("INTEGRATION_INSTALL_USE_LOCAL") or "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("editable local install — git path check skipped")
    customer_install_sequence(openai_agents_install_env)
    origin = installed_package_path(openai_agents_install_env, "ollie_integrations_openai_agents")
    assert origin is not None
    origin_path = origin.replace("\\", "/")
    venv_root = str(openai_agents_install_env["venv_dir"]).replace("\\", "/")
    repo_src = str(_PACKAGE_DIR / "src").replace("\\", "/")
    assert venv_root in origin_path, f"expected install under venv, got {origin_path}"
    assert repo_src not in origin_path, f"must not load editable src, got {origin_path}"
