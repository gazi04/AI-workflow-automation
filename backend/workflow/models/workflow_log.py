from datetime import datetime, timezone
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from core.database import Base

import uuid


if TYPE_CHECKING:
    from workflow.models.workflow_run import WorkflowRun

class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    level: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)

    run: Mapped["WorkflowRun"] = relationship("workflow.models.workflow_run.WorkflowRun", back_populates="logs")

    __table_args__ = (
        CheckConstraint("level IN ('info', 'warning', 'error', 'debug')"),
    )

