"""Unit tests for the system-maintenance deployment registrations
(renew-gmail-watches, cleanup-expired-auth) called from main.py's lifespan."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from prefect.client.schemas.schedules import CronSchedule

from scripts.register_renewal import (
    register_renewal_deployment,
    register_cleanup_deployment,
)


async def test_registers_cleanup_daily_cron_deployment():
    flow_mock = MagicMock()
    deployment_id = uuid4()
    flow_mock.deploy = AsyncMock(return_value=deployment_id)

    with patch("scripts.register_renewal.cleanup_expired_auth") as flow_cls:
        flow_cls.from_source = AsyncMock(return_value=flow_mock)
        result = await register_cleanup_deployment()

    assert result == deployment_id
    flow_mock.deploy.assert_awaited_once()
    kwargs = flow_mock.deploy.await_args.kwargs
    assert kwargs["name"] == "cleanup-expired-auth-daily"
    assert kwargs["work_pool_name"] == "my-process-pool"
    assert isinstance(kwargs["schedule"], CronSchedule)
    assert kwargs["schedule"].cron == "15 3 * * *"


async def test_registers_daily_cron_deployment():
    flow_mock = MagicMock()
    deployment_id = uuid4()
    flow_mock.deploy = AsyncMock(return_value=deployment_id)

    with patch(
        "scripts.register_renewal.renew_gmail_watches"
    ) as flow_cls:
        flow_cls.from_source = AsyncMock(return_value=flow_mock)
        result = await register_renewal_deployment()

    assert result == deployment_id
    flow_mock.deploy.assert_awaited_once()
    kwargs = flow_mock.deploy.await_args.kwargs
    assert kwargs["name"] == "renew-gmail-watches-daily"
    assert kwargs["work_pool_name"] == "my-process-pool"
    assert isinstance(kwargs["schedule"], CronSchedule)
    assert kwargs["schedule"].cron == "0 3 * * *"


async def test_retries_then_succeeds_when_prefect_not_ready():
    flow_mock = MagicMock()
    deployment_id = uuid4()
    # First attempt fails (prefect API not up yet), second succeeds.
    flow_mock.deploy = AsyncMock(
        side_effect=[ConnectionError("prefect down"), deployment_id]
    )

    with (
        patch("scripts.register_renewal.renew_gmail_watches") as flow_cls,
        patch("scripts.register_renewal.asyncio.sleep", new=AsyncMock()),
    ):
        flow_cls.from_source = AsyncMock(return_value=flow_mock)
        result = await register_renewal_deployment(retries=3, delay=0)

    assert result == deployment_id
    assert flow_mock.deploy.await_count == 2


async def test_raises_after_exhausting_retries():
    flow_mock = MagicMock()
    flow_mock.deploy = AsyncMock(side_effect=ConnectionError("prefect down"))

    with (
        patch("scripts.register_renewal.renew_gmail_watches") as flow_cls,
        patch("scripts.register_renewal.asyncio.sleep", new=AsyncMock()),
    ):
        flow_cls.from_source = AsyncMock(return_value=flow_mock)
        with pytest.raises(ConnectionError):
            await register_renewal_deployment(retries=2, delay=0)

    assert flow_mock.deploy.await_count == 2
