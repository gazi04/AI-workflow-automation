from uuid import UUID
from typing import Optional, List

from sqlalchemy.orm import Session

from workflow.models.workflow_run_record import WorkflowRunRecord


class WorkflowRunService:
    @staticmethod
    def create(
        db: Session,
        *,
        workflow_id: UUID,
        user_id: UUID,
        node_results: dict,
        status: str,
        prefect_run_id: Optional[UUID] = None,
        trigger_data: Optional[dict] = None,
        duration_ms: Optional[int] = None,
    ) -> WorkflowRunRecord:
        record = WorkflowRunRecord(
            workflow_id=workflow_id,
            user_id=user_id,
            prefect_run_id=prefect_run_id,
            trigger_data=trigger_data,
            node_results=node_results,
            status=status,
            duration_ms=duration_ms,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_by_prefect_run_id(
        db: Session, prefect_run_id: UUID, user_id: UUID
    ) -> Optional[WorkflowRunRecord]:
        """Fetch a single audit record by its Prefect run id, scoped to the owner.

        Filtering on user_id enforces ownership in the query, so a non-owner gets
        None (treated as 404 by the route — no existence leak)."""
        return (
            db.query(WorkflowRunRecord)
            .filter(
                WorkflowRunRecord.prefect_run_id == prefect_run_id,
                WorkflowRunRecord.user_id == user_id,
            )
            .first()
        )

    @staticmethod
    def get_undelivered_failures(db: Session, user_id: UUID) -> List[WorkflowRunRecord]:
        """Runs that failed (fully or partially) and whose node_failed event has
        not yet been broadcast to the user."""
        return (
            db.query(WorkflowRunRecord)
            .filter(
                WorkflowRunRecord.user_id == user_id,
                WorkflowRunRecord.status.in_(("failed", "partial")),
                WorkflowRunRecord.failure_notified.is_(False),
            )
            .all()
        )

    @staticmethod
    def mark_notified(db: Session, ids: List[UUID]) -> None:
        if not ids:
            return
        db.query(WorkflowRunRecord).filter(WorkflowRunRecord.id.in_(ids)).update(
            {WorkflowRunRecord.failure_notified: True}, synchronize_session=False
        )
        db.commit()
