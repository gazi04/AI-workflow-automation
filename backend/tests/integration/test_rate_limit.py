"""Integration test for slowapi rate limiting.

Rate limiting is disabled suite-wide in conftest (so shared endpoints don't
flake); this test re-enables it in its own scope and confirms the limiter
returns 429 once the per-minute budget is exhausted.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.rate_limit import limiter
from main import app


@pytest.fixture
def rate_limited():
    """Enable the limiter for this test only, with a clean counter store."""
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = False


def test_ai_health_returns_429_past_limit(rate_limited):
    # /ai/health is capped at 30/minute and touches no DB, so a bare TestClient
    # (no db_session fixture) suffices. Patch the service so no real Azure
    # client is constructed — we only care about the limiter here.
    with (
        patch(
            "ai.routes.ai_router.AiService.health_check",
            return_value={"status": "healthy", "azure_connected": True},
        ),
        TestClient(app) as bare_client,
    ):
        statuses = [bare_client.get("/api/ai/health").status_code for _ in range(31)]

    assert statuses[:30] == [200] * 30
    assert statuses[-1] == 429
