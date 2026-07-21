from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from prefect.exceptions import ObjectNotFound

from orchestration.services.deployment_service import DeploymentService


def _patched_client(delete_side_effect):
    client = MagicMock()
    client.delete_deployment = AsyncMock(side_effect=delete_side_effect)

    @asynccontextmanager
    async def fake_get_client():
        yield client

    return patch(
        "orchestration.services.deployment_service.get_client", fake_get_client
    ), client


async def test_delete_swallows_object_not_found():
    """A deployment already gone in Prefect is treated as a successful delete."""
    dep_id = uuid4()
    ctx, client = _patched_client(ObjectNotFound(Exception("gone")))
    with ctx:
        await DeploymentService.delete(dep_id)  # must not raise
    client.delete_deployment.assert_awaited_once_with(dep_id)


async def test_delete_propagates_other_errors():
    """A real Prefect failure still surfaces."""
    dep_id = uuid4()
    ctx, _ = _patched_client(RuntimeError("prefect down"))
    with ctx, pytest.raises(RuntimeError):
        await DeploymentService.delete(dep_id)
