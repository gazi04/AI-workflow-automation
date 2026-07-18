from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from processed_messages.models.processed_messages import ProcessedMessages
from user.models.user import User
from workflow.models.workflow import Workflow
from workflow.services import WorkflowService


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


async def _processed_ids(db: AsyncSession, workflow_id) -> list:
    result = await db.execute(
        select(ProcessedMessages.id).where(
            ProcessedMessages.workflow_id == workflow_id
        )
    )
    return list(result.scalars().all())


async def test_deleting_workflow_cascades_to_processed_messages(
    db_session, test_workflow
):
    """delete_by_id issues a Core DELETE, which bypasses ORM cascades — only the
    DB-level ON DELETE CASCADE cleans these up."""
    db_session.add(
        ProcessedMessages(message_id="msg_1", workflow_id=test_workflow.id)
    )
    db_session.add(
        ProcessedMessages(message_id="msg_2", workflow_id=test_workflow.id)
    )
    await db_session.flush()
    assert len(await _processed_ids(db_session, test_workflow.id)) == 2

    await WorkflowService.delete_by_id(db_session, test_workflow.id)
    await db_session.flush()

    assert await _processed_ids(db_session, test_workflow.id) == []


async def test_processed_message_for_unknown_workflow_is_rejected(db_session):
    """The FK stops orphans being created in the first place."""
    db_session.add(ProcessedMessages(message_id="msg_1", workflow_id=uuid4()))

    with pytest.raises(IntegrityError):
        await db_session.flush()
