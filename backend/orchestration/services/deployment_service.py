from typing import Any, Dict, List, Optional
from uuid import UUID
from prefect import get_client
from prefect.client.schemas import FlowRun
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterDeploymentId
from prefect.deployments import run_deployment
from prefect.client.schemas.actions import DeploymentUpdate
from prefect.client.schemas.schedules import CronSchedule
from core.setup_logging import setup_logger
from orchestration.flows.master_flow import execute_automation_flow
from workflow.schemas import WorkflowDefinition

logger = setup_logger("Deployment Service")


class DeploymentService:
    @staticmethod
    async def run(workflow_id: UUID, config: Optional[Dict[str, Any]] = None):
        """
        Run a prefect deployment
        """
        try:
            await run_deployment(workflow_id, parameters=config)
            logger.info(f"Triggering workflow {workflow_id}")
        except Exception as e:
            logger.debug(f"Unexpected error occurred: \n{e}")
            raise e

    @staticmethod
    async def create_deployment_for_workflow(
        user_id: UUID, workflow: WorkflowDefinition
    ) -> UUID:
        """
        Dynamically registers a deployment with Prefect.
        """
        trigger = workflow.trigger
        trigger_type = trigger.type

        schedule = None
        if trigger_type == "schedule":
            cron_expression = trigger.config.cron
            if cron_expression:
                schedule = CronSchedule(cron=cron_expression, timezone="UTC")

        safe_name = workflow.name.replace(" ", "-").lower()
        deployment_name = f"user-{user_id}-{safe_name}"
        workflow_data = workflow.model_dump()

        flow_from_source = await execute_automation_flow.from_source(
            source=".",
            entrypoint="orchestration/flows/master_flow.py:execute_automation_flow",
        )

        deployment_id = await flow_from_source.deploy(
            name=deployment_name,
            parameters={"user_id": str(user_id), "workflow_data": workflow_data},
            schedule=schedule,
            tags=["user-generated"],
            work_pool_name="my-process-pool",
            build=False,
        )

        print(f"✅ Deployment created: {deployment_name} (ID: {deployment_id})")
        return deployment_id

    @staticmethod
    async def toggle_workflow(deployment_id: UUID, active: bool) -> Dict:
        """
        Toggles prefect deployments into active and not active states
        active=True -> Resume
        active=False -> Pause
        """
        async with get_client() as client:
            await client.update_deployment(
                deployment_id=deployment_id,
                deployment=DeploymentUpdate(paused=not active),
            )
            return {"status": "success", "is_active": active}

    @staticmethod
    async def update_workflow_config(deployment_id: UUID, new_params: Dict) -> Dict:
        """
        Updates the parameters of a deployment
        """
        async with get_client() as client:
            deployment = await client.read_deployment(deployment_id)

            updated_params = deployment.parameters or {}
            updated_params.update(new_params)

            await client.update_deployment(
                deployment_id=deployment_id,
                deployment=DeploymentUpdate(parameters=updated_params),
            )
            return {"status": "updated", "parameters": updated_params}

    @staticmethod
    async def delete(id: UUID):
        """
        Deletes deployment
        """
        async with get_client() as client:
            await client.delete_deployment(id)


    @staticmethod
    async def get_workflow_history(id: UUID) -> List[FlowRun]:
        async with get_client() as client:
            return await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    deployment_id=FlowRunFilterDeploymentId(any_=[id])
                ),
                limit=20,
                sort="START_TIME_DESC"
            )
