from uuid import UUID
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workflow.models.workflow_run_record import WorkflowRunRecord


class WorkflowRunService:
    @staticmethod
    async def create(
        db: AsyncSession,
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
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_by_prefect_run_id(
        db: AsyncSession, prefect_run_id: UUID, user_id: UUID
    ) -> Optional[WorkflowRunRecord]:
        """Fetch a single audit record by its Prefect run id, scoped to the owner.

        Filtering on user_id enforces ownership in the query, so a non-owner gets
        None (treated as 404 by the route — no existence leak)."""
        result = await db.execute(
            select(WorkflowRunRecord).where(
                WorkflowRunRecord.prefect_run_id == prefect_run_id,
                WorkflowRunRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_undelivered_failures(db: AsyncSession, user_id: UUID) -> List[WorkflowRunRecord]:
        """Runs that failed (fully or partially) and whose node_failed event has
        not yet been broadcast to the user."""
        result = await db.execute(
            select(WorkflowRunRecord).where(
                WorkflowRunRecord.user_id == user_id,
                WorkflowRunRecord.status.in_(("failed", "partial")),
                WorkflowRunRecord.failure_notified.is_(False),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_notified(db: AsyncSession, ids: List[UUID]) -> None:
        if not ids:
            return
        await db.execute(
            update(WorkflowRunRecord)
            .where(WorkflowRunRecord.id.in_(ids))
            .values(failure_notified=True)
        )
        await db.commit()
