from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processed_messages.models.processed_messages import ProcessedMessages


class ProcessedMessageService:
    @staticmethod
    async def create(db: AsyncSession, message_id: str, workflow_id: UUID):
        new_processed_message = ProcessedMessages(
            message_id=message_id, workflow_id=workflow_id
        )
        db.add(new_processed_message)
        await db.commit()
        await db.refresh(new_processed_message)
        return new_processed_message

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
