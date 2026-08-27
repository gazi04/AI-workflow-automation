from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from processed_messages.models.processed_messages import ProcessedMessages


class ProcessedMessageService:
    @staticmethod
    async def create(
        db: AsyncSession, message_id: str, workflow_id: UUID
    ) -> Optional[UUID]:
        """Record a (message, workflow) pair as handled.

        A concurrent drain claiming the same pair is an expected outcome of the
        defer-and-drain design, not an error — ON CONFLICT DO NOTHING makes the
        duplicate a no-op instead of a unique violation that aborts the
        transaction and forces the caller to roll back.

        Returns the new row's id, or None if someone else got there first.
        """
        stmt = (
            pg_insert(ProcessedMessages)
            .values(message_id=message_id, workflow_id=workflow_id)
            .on_conflict_do_nothing(index_elements=["message_id", "workflow_id"])
            .returning(ProcessedMessages.id)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_message_id_and_workflow_id(
        db: AsyncSession, message_id: str, workflow_id: UUID
    ) -> Optional[ProcessedMessages]:
        result = await db.execute(
            select(ProcessedMessages).where(
                ProcessedMessages.message_id == message_id,
                ProcessedMessages.workflow_id == workflow_id,
            )
        )
        return result.scalar_one_or_none()
