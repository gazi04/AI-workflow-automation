from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class ProcessedMessages(Base):
    __tablename__ = "processed_messages"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    message_id: Mapped[str] = mapped_column(String(), nullable=False)
    workflow_id: Mapped[UUID] = mapped_column(UUID(), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("message_id", "workflow_id", name="uq_message_workflow_pair"),
    )
