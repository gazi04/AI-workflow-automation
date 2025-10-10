from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, TYPE_CHECKING

from core.database import Base

import uuid


if TYPE_CHECKING:
    from workflow.models.workflow import Workflow
    from workflow.models.workflow_log import WorkflowLog

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    context_data: Mapped[dict] = mapped_column(JSONB)

    workflow: Mapped["Workflow"] = relationship("workflow.models.workflow.Workflow", back_populates="runs")
    logs: Mapped[List["WorkflowLog"]] = relationship(
        "workflow.models.workflow_log.WorkflowLog",
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("status IN ('success', 'failure', 'running')"),)
