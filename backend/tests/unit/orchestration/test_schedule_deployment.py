"""Unit test for the schedule-trigger → Prefect CronSchedule wiring in
DeploymentService.create_deployment_for_workflow."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prefect.client.schemas.schedules import CronSchedule

from orchestration.services.deployment_service import DeploymentService
from workflow.schemas import WorkflowSchema


def _schedule_schema(cron: str = "0 9 * * *") -> WorkflowSchema:
    return WorkflowSchema.model_validate(
        {
            "name": "Daily Digest",
            "description": "",
            "execution_config": {
                "start_node_ids": ["t1"],
                "nodes": {
                    "t1": {
                        "id": "t1",
                        "type": "trigger",
                        "config": {"type": "schedule", "config": {"cron": cron}},
                    },
                    "a1": {
                        "id": "a1",
                        "type": "action",
                        "config": {
                            "type": "send_email",
                            "config": {
                                "to": "x@example.com",
                                "subject": "s",
                                "body": "b",
                            },
                        },
                    },
                },
                "edges": [{"id": "e1", "source": "t1", "target": "a1"}],
            },
        }
    )


async def test_schedule_trigger_creates_cron_schedule():
    flow_mock = MagicMock()
    flow_mock.deploy = AsyncMock(return_value=uuid4())

    with patch(
        "orchestration.services.deployment_service.execute_automation_flow"
    ) as flow_cls:
        flow_cls.from_source = AsyncMock(return_value=flow_mock)
        await DeploymentService.create_deployment_for_workflow(
            uuid4(), _schedule_schema("0 9 * * *")
        )

    schedule = flow_mock.deploy.await_args.kwargs["schedule"]
    assert isinstance(schedule, CronSchedule)
    assert schedule.cron == "0 9 * * *"
