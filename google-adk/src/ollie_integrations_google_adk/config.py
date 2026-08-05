"""Hosted Ollie defaults (same for all customers on our Render stack)."""

from __future__ import annotations

import os

# Override via env for staging/local; customers on hosted Ollie do not need to set these.
DEFAULT_OLLIE_BASE_URL = "https://olliemainapi.onrender.com"
DEFAULT_OLLIE_INGEST_BASE_URL = "https://olliejudge-sentry-backend.onrender.com"


def resolve_base_url(explicit: str | None = None) -> str:
    return (explicit or os.getenv("OLLIE_BASE_URL") or DEFAULT_OLLIE_BASE_URL).strip()


def resolve_ingest_base_url(explicit: str | None = None) -> str:
    return (
        explicit or os.getenv("OLLIE_INGEST_BASE_URL") or DEFAULT_OLLIE_INGEST_BASE_URL
    ).strip()


def create_ollie_client(
    *,
    api_key: str | None = None,
    agent_id: str | None = None,
    base_url: str | None = None,
    ingest_base_url: str | None = None,
):
    """Build ollie.Client with hosted defaults; customer only supplies key + agent id."""
    import ollie

    return ollie.Client(
        api_key=api_key,
        agent_id=agent_id,
        base_url=resolve_base_url(base_url),
        ingest_base_url=resolve_ingest_base_url(ingest_base_url),
    )
