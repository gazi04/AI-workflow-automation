"""Register the daily system-maintenance deployments with Prefect.

Run manually (and after any change to the flows) from `backend/`:

    uv run python -m scripts.register_renewal

Also imported by `main.py`'s lifespan so a `docker compose up` registers the
deployments automatically. Requires the `my-process-pool` worker to execute
scheduled runs.
"""

import asyncio

from prefect.schedules import Cron

from orchestration.flows.renew_watches_flow import renew_gmail_watches
from orchestration.flows.cleanup_auth_flow import cleanup_expired_auth


async def register_renewal_deployment(retries: int = 5, delay: float = 3.0):
    """Register (or refresh) the daily renew-gmail-watches deployment.

    Idempotent: `.deploy()` upserts by deployment name, so calling this on every
    backend boot just refreshes the existing deployment. Retries because
    prefect-server may not be reachable the instant the backend starts (compose
    `depends_on` is `service_started`, not ready).
    """
    flow_from_source = await renew_gmail_watches.from_source(  # pyright: ignore[reportGeneralTypeIssues]
        source=".",
        entrypoint="orchestration/flows/renew_watches_flow.py:renew_gmail_watches",
    )

    last_err = None
    for _ in range(retries):
        try:
            return await flow_from_source.deploy(  # pyright: ignore[reportGeneralTypeIssues]
                name="renew-gmail-watches-daily",
                schedule=Cron("0 3 * * *", timezone="UTC"),  # daily 03:00 UTC
                tags=["system", "gmail-maintenance"],
                work_pool_name="my-process-pool",
                build=False,
            )
        except Exception as e:  # prefect API not up yet / transient
            last_err = e
            await asyncio.sleep(delay)

    assert last_err is not None
    raise last_err


async def register_cleanup_deployment(retries: int = 5, delay: float = 3.0):
    """Register (or refresh) the daily expired-auth cleanup deployment.

    Same idempotent-upsert + retry contract as `register_renewal_deployment`.
    """
    flow_from_source = await cleanup_expired_auth.from_source(  # pyright: ignore[reportGeneralTypeIssues]
        source=".",
        entrypoint="orchestration/flows/cleanup_auth_flow.py:cleanup_expired_auth",
    )

    last_err = None
    for _ in range(retries):
        try:
            return await flow_from_source.deploy(  # pyright: ignore[reportGeneralTypeIssues]
                name="cleanup-expired-auth-daily",
                schedule=Cron("15 3 * * *", timezone="UTC"),  # daily 03:15 UTC
                tags=["system", "auth-maintenance"],
                work_pool_name="my-process-pool",
                build=False,
            )
        except Exception as e:  # prefect API not up yet / transient
            last_err = e
            await asyncio.sleep(delay)

    assert last_err is not None
    raise last_err


async def main():
    renewal_id = await register_renewal_deployment()
    print(f"✅ Deployment registered: renew-gmail-watches-daily (ID: {renewal_id})")
    cleanup_id = await register_cleanup_deployment()
    print(f"✅ Deployment registered: cleanup-expired-auth-daily (ID: {cleanup_id})")


if __name__ == "__main__":
    asyncio.run(main())
