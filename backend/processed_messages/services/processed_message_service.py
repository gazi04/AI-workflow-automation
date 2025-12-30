from uuid import UUID
from sqlalchemy.orm import Session

from processed_messages.models.processed_messages import ProcessedMessages


class ProcessedMessageService:
    @staticmethod
    async def create(db: Session, message_id: str, workflow_id: UUID):
        new_processed_message = ProcessedMessages(
            message_id=message_id, workflow_id=workflow_id
        )
        db.add(new_processed_message)
        db.commit()
        db.refresh(new_processed_message)
        return new_processed_message

    @staticmethod
    async def get_by_message_id_and_workflow_id(
        db: Session, message_id: str, workflow_id: UUID
    ) -> ProcessedMessages:
        processed_message = (
            db.query(ProcessedMessages)
            .filter(
                ProcessedMessages.message_id == message_id,
                ProcessedMessages.workflow_id == workflow_id
            )
            .first()
        )

        return processed_message
