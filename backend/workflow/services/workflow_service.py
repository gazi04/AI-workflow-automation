from uuid import UUID
from sqlalchemy.orm import Session

from workflow.models.workflow import Workflow


class WorkflowService:
    @staticmethod
    async def create(
            db: Session,
            workflow_id: UUID,
            user_id: UUID,
            name: str,
            description: str,
            workflow_definition: dict
    ) -> Workflow:
        new_workflow = Workflow(
            id = workflow_id,
            user_id = user_id,
            name = name,
            description = description,
            ai_generated_definition = workflow_definition
        )
        db.add(new_workflow)
        db.commit()
        db.refresh(new_workflow)
        return new_workflow
