from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from user.models.user import User
from workflow.models.workflow import Workflow
from workflow.services import WorkflowRunService


@pytest.fixture
async def test_workflow(db_session: AsyncSession, test_user: User) -> Workflow:
    workflow = Workflow(
        id=uuid4(),
        user_id=test_user.id,
        name="WF",
        description="d",
        is_active=True,
        config={},
    )
    db_session.add(workflow)
    await db_session.flush()
    return workflow


def _node_results(status="failed"):
    return {"node_1": {"output": None, "status": status, "error": "boom"}}


async def test_create_round_trips(db_session, test_user, test_workflow):
    record = await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="failed",
        duration_ms=42,
    )

    assert record.id is not None
    assert record.workflow_id == test_workflow.id
    assert record.user_id == test_user.id
    assert record.status == "failed"
    assert record.duration_ms == 42
    assert record.failure_notified is False
    assert record.node_results["node_1"]["error"] == "boom"


async def test_get_undelivered_failures_filters_status_and_flag(
    db_session, test_user, test_workflow
):
    failed = await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results("failed"),
        status="failed",
    )
    await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results("success"),
        status="success",
    )

    rows = await WorkflowRunService.get_undelivered_failures(db_session, test_user.id)

    ids = {r.id for r in rows}
    assert failed.id in ids
    assert all(r.status in ("failed", "partial") for r in rows)


async def test_get_undelivered_failures_scoped_to_user(
    db_session, test_user, second_user, test_workflow
):
    await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="failed",
    )

    rows = await WorkflowRunService.get_undelivered_failures(db_session, second_user.id)

    assert rows == []


async def test_get_by_prefect_run_id_returns_owner_record(
    db_session, test_user, test_workflow
):
    prefect_run_id = uuid4()
    record = await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results("success"),
        status="success",
        prefect_run_id=prefect_run_id,
    )

    found = await WorkflowRunService.get_by_prefect_run_id(
        db_session, prefect_run_id, test_user.id
    )

    assert found is not None
    assert found.id == record.id


async def test_get_by_prefect_run_id_scoped_to_user(
    db_session, test_user, second_user, test_workflow
):
    prefect_run_id = uuid4()
    await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="failed",
        prefect_run_id=prefect_run_id,
    )

    found = await WorkflowRunService.get_by_prefect_run_id(
        db_session, prefect_run_id, second_user.id
    )

    assert found is None


async def test_get_by_prefect_run_id_unknown_returns_none(db_session, test_user):
    assert (
        await WorkflowRunService.get_by_prefect_run_id(db_session, uuid4(), test_user.id)
        is None
    )


async def test_mark_notified_flips_flag(db_session, test_user, test_workflow):
    record = await WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="partial",
    )

    await WorkflowRunService.mark_notified(db_session, [record.id])

    rows = await WorkflowRunService.get_undelivered_failures(db_session, test_user.id)
    assert record.id not in {r.id for r in rows}
