from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from user.models.user import User
from workflow.models.workflow import Workflow
from workflow.services import WorkflowRunService


@pytest.fixture
def test_workflow(db_session: Session, test_user: User) -> Workflow:
    workflow = Workflow(
        id=uuid4(),
        user_id=test_user.id,
        name="WF",
        description="d",
        is_active=True,
        config={},
    )
    db_session.add(workflow)
    db_session.flush()
    return workflow


def _node_results(status="failed"):
    return {"node_1": {"output": None, "status": status, "error": "boom"}}


def test_create_round_trips(db_session, test_user, test_workflow):
    record = WorkflowRunService.create(
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


def test_get_undelivered_failures_filters_status_and_flag(
    db_session, test_user, test_workflow
):
    failed = WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results("failed"),
        status="failed",
    )
    WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results("success"),
        status="success",
    )

    rows = WorkflowRunService.get_undelivered_failures(db_session, test_user.id)

    ids = {r.id for r in rows}
    assert failed.id in ids
    assert all(r.status in ("failed", "partial") for r in rows)


def test_get_undelivered_failures_scoped_to_user(
    db_session, test_user, second_user, test_workflow
):
    WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="failed",
    )

    rows = WorkflowRunService.get_undelivered_failures(db_session, second_user.id)

    assert rows == []


def test_mark_notified_flips_flag(db_session, test_user, test_workflow):
    record = WorkflowRunService.create(
        db_session,
        workflow_id=test_workflow.id,
        user_id=test_user.id,
        node_results=_node_results(),
        status="partial",
    )

    WorkflowRunService.mark_notified(db_session, [record.id])

    rows = WorkflowRunService.get_undelivered_failures(db_session, test_user.id)
    assert record.id not in {r.id for r in rows}
