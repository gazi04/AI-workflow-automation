import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class WorkflowRunRecord(Base):
    """Persistent per-run audit record.

    Distinct from the Prefect-derived ``WorkflowRun`` Pydantic schema: this table
    stores what each node actually produced (or failed with) so the failure can be
    surfaced to the user and inspected later — something Prefect's run state alone
    cannot provide.
    """

    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # The Prefect flow-run id, when running inside a Prefect context. Null for
    # direct ``.fn`` invocations (unit tests).
    prefect_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    trigger_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # { node_id: { "output": ..., "status": "success"|"failed", "error": ... } }
    node_results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # "success" | "partial" | "failed"
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Dedup flag: the WebSocket poll loop flips this once it has broadcast the
    # node_failed event(s) for this run.
    failure_notified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
