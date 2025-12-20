from uuid import UUID
from prefect.client.schemas.schedules import CronSchedule
from orchestration.flows.master_flow import execute_automation_flow

class DeploymentService:
    @staticmethod
    async def create_deployment_for_workflow(user_id: UUID, workflow_name: str, workflow_data: dict):
        """
        Dynamically registers a deployment with Prefect.
        """
        trigger_data = workflow_data.get("trigger", {})
        trigger_type = trigger_data.get("type")
        
        schedule = None
        if trigger_type == "schedule":
            cron_expression = trigger_data.get("config", {}).get("cron")
            if cron_expression:
                schedule = CronSchedule(cron=cron_expression, timezone="UTC")

        safe_name = workflow_name.replace(" ", "-").lower()
        deployment_name = f"user-{user_id}-{safe_name}"

        flow_from_source = await execute_automation_flow.from_source(
            source=".",
            entrypoint="orchestration/flows/master_flow.py:execute_automation_flow"
        )

        deployment_id = await flow_from_source.deploy(
            name=deployment_name,
            parameters={
                "user_id": str(user_id),
                "workflow_data": workflow_data
            },
            schedule=schedule,
            tags=["user-generated"],
            work_pool_name="my-process-pool" ,
            build=False
        )

        print(f"✅ Deployment created: {deployment_name} (ID: {deployment_id})")
        return str(deployment_id)
