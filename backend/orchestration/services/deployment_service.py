from typing import Any, Dict, List, Optional
from uuid import UUID
from prefect import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterTags,
    LogFilter,
    LogFilterFlowRunId,
)
from prefect.client.schemas.objects import Log
from prefect.client.schemas.sorting import FlowRunSort, LogSort
from prefect.deployments import run_deployment
from prefect.client.schemas.actions import DeploymentUpdate
from prefect.client.schemas.schedules import CronSchedule
from core.setup_logging import setup_logger
from orchestration.flows.master_flow import execute_automation_flow
from utils.translate_workflow_runs_schema import translate_flow_runs_schema
from workflow.schemas import (
    WorkflowRun,
)
from workflow.schemas import WorkflowSchema

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
        user_id: UUID, schema: WorkflowSchema
    ) -> UUID:
        """
        Dynamically registers a deployment with Prefect.
        Supports multiple triggers (DAG architecture).
        """
        schedule = None
        workflow = schema.execution_config

        for node_id in workflow.start_node_ids:
            node = workflow.nodes.get(node_id)
            if not node or node.type != "trigger":
                continue

            trigger = node.config

            if trigger.type == "schedule":
                cron_expression = (
                    getattr(trigger, "config", trigger).cron
                    if hasattr(getattr(trigger, "config", trigger), "cron")
                    else getattr(trigger, "cron", None)
                )

                if cron_expression and schedule is None:
                    # Note: Prefect deploy() param 'schedule' takes a single schedule.
                    # If a user adds multiple schedule nodes, we use the first one here.
                    schedule = CronSchedule(cron=cron_expression, timezone="UTC")

        safe_name = schema.name.replace(" ", "-").lower()
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
            tags=["user-generated", f"user-{user_id}"],
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
        Updates the parameters of a specific Prefect deployment.
        This method is now 'leak-proof': it identifies the core parameters (user_id)
        and updates the 'workflow_data' while purging any legacy flattened keys
        that would cause a SignatureMismatchError.
        """
        async with get_client() as client:
            deployment = await client.read_deployment(deployment_id)
            current_params = deployment.parameters or {}

            # Construct a clean, nested parameter set
            updated_params = {
                "user_id": current_params.get("user_id"),
                "workflow_data": new_params,
                # trigger_context is usually transient, but we preserve it if present
                "trigger_context": current_params.get("trigger_context"),
            }

            # Remove keys where value is None to keep the deployment clean
            updated_params = {k: v for k, v in updated_params.items() if v is not None}

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
    async def get_history(user_id: UUID) -> List[WorkflowRun]:
        async with get_client() as client:
            flow_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    tags=FlowRunFilterTags(
                        all_=["user-generated"],
                        any_=[f"user-{user_id}", f"user_{user_id}"],
                    ),
                ),
                limit=50,
                sort=FlowRunSort.START_TIME_DESC,
            )

            return translate_flow_runs_schema(flow_runs)

    @staticmethod
    async def get_workflow_history(id: UUID) -> List[WorkflowRun]:
        async with get_client() as client:
            flow_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    deployment_id=FlowRunFilterDeploymentId(any_=[id]),
                    tags=FlowRunFilterTags(all_=["user-generated"]),
                ),
                limit=50,
                sort=FlowRunSort.START_TIME_DESC,
            )

            return translate_flow_runs_schema(flow_runs)

    @staticmethod
    async def get_run_logs(run_id: UUID) -> List[Log]:
        """Fetches the raw logs for a specific flow run from Prefect"""
        async with get_client() as client:
            return await client.read_logs(
                log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=[run_id])),
                sort=LogSort.TIMESTAMP_ASC,
            )

    @staticmethod
    async def get_latest_runs_status(
        user_id: UUID, limit: int = 5
    ) -> List[WorkflowRun]:
        """
        A lightweight fetcher specifically for the frontend polling mechanism.
        Used to detect status changes (like 'Failed') to trigger toasts.
        """
        async with get_client() as client:
            flow_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    tags=FlowRunFilterTags(
                        all_=["user-generated"],
                        any_=[f"user-{user_id}", f"user_{user_id}"],
                    ),
                ),
                limit=limit,
                sort=FlowRunSort.START_TIME_DESC,
            )
            return translate_flow_runs_schema(flow_runs)
