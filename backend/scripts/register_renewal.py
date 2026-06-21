"""Register the daily Gmail-watch renewal deployment with Prefect.

Run once (and after any change to the flow) from `backend/`:

    uv run python -m scripts.register_renewal

Requires the `my-process-pool` worker to execute scheduled runs.
"""

import asyncio

from prefect.client.schemas.schedules import CronSchedule

from orchestration.flows.renew_watches_flow import renew_gmail_watches


async def main():
    flow_from_source = await renew_gmail_watches.from_source(
        source=".",
        entrypoint="orchestration/flows/renew_watches_flow.py:renew_gmail_watches",
    )

    deployment_id = await flow_from_source.deploy(
        name="renew-gmail-watches-daily",
        schedule=CronSchedule(cron="0 3 * * *", timezone="UTC"),  # daily 03:00 UTC
        tags=["system", "gmail-maintenance"],
        work_pool_name="my-process-pool",
        build=False,
    )

    print(f"✅ Deployment registered: renew-gmail-watches-daily (ID: {deployment_id})")


if __name__ == "__main__":
    asyncio.run(main())
