"""Register the daily Gmail-watch renewal deployment with Prefect.

Run manually (and after any change to the flow) from `backend/`:

    uv run python -m scripts.register_renewal

Also imported by `main.py`'s lifespan so a `docker compose up` registers the
deployment automatically. Requires the `my-process-pool` worker to execute
scheduled runs.
"""

import asyncio

from prefect.client.schemas.schedules import CronSchedule

from orchestration.flows.renew_watches_flow import renew_gmail_watches


async def register_renewal_deployment(retries: int = 5, delay: float = 3.0):
    """Register (or refresh) the daily renew-gmail-watches deployment.

    Idempotent: `.deploy()` upserts by deployment name, so calling this on every
    backend boot just refreshes the existing deployment. Retries because
    prefect-server may not be reachable the instant the backend starts (compose
    `depends_on` is `service_started`, not ready).
    """
    flow_from_source = await renew_gmail_watches.from_source(
        source=".",
        entrypoint="orchestration/flows/renew_watches_flow.py:renew_gmail_watches",
    )

    last_err = None
    for _ in range(retries):
        try:
            return await flow_from_source.deploy(
                name="renew-gmail-watches-daily",
                schedule=CronSchedule(cron="0 3 * * *", timezone="UTC"),  # daily 03:00 UTC
                tags=["system", "gmail-maintenance"],
                work_pool_name="my-process-pool",
                build=False,
            )
        except Exception as e:  # prefect API not up yet / transient
            last_err = e
            await asyncio.sleep(delay)

    raise last_err


async def main():
    deployment_id = await register_renewal_deployment()
    print(f"✅ Deployment registered: renew-gmail-watches-daily (ID: {deployment_id})")


if __name__ == "__main__":
    asyncio.run(main())
