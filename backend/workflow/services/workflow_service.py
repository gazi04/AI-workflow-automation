from typing import Dict, List
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
            config = workflow_definition
        )
        db.add(new_workflow)
        db.commit()
        db.refresh(new_workflow)
        return new_workflow

    @staticmethod
    async def update_status(db: Session, id: UUID, status: bool) -> Workflow:
        workflow = db.query(Workflow).filter(Workflow.id == id).first()

        if workflow:
            workflow.status = status
            # we use flush because workflow and deployment services are sequantially dependent 
            db.flush() # in the workflow router the changes are commited

        return workflow

    @staticmethod
    async def update_config(db: Session, id: UUID, config: Dict) -> Workflow:
        workflow = db.query(Workflow).filter(Workflow.id == id).first()

        if workflow:
            workflow.config = config
            # we use flush because workflow and deployment services are sequantially dependent 
            db.flush() # in the workflow router the changes are commited

        return workflow

    @staticmethod
    async def get_by_user_id(db: Session, id: UUID) -> List[Workflow]:
        return db.query(Workflow).filter(Workflow.user_id == id).all()

