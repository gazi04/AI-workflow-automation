from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from workflow.models.workflow import Workflow
from workflow.schemas import WorkflowSchema


class WorkflowService:
    @staticmethod
    def create(db: Session, workflow_id: UUID, user_id: UUID, schema: WorkflowSchema) -> Workflow:
        new_workflow = Workflow(
            id=workflow_id,
            user_id=user_id,
            name=schema.name,
            description=schema.description,
            config=schema.execution_config.model_dump(),
            ui_metadata=schema.ui_metadata.model_dump() if schema.ui_metadata else {},
            version=1
        )
        db.add(new_workflow)
        db.commit()
        db.refresh(new_workflow)
        return new_workflow

    @staticmethod
    def update_is_active(db: Session, id: UUID, is_active: bool) -> Workflow:
        workflow = db.query(Workflow).filter(Workflow.id == id).first()

        if workflow:
            workflow.is_active = is_active
            # we use flush because workflow and deployment services are sequantially dependent
            db.flush()  # in the workflow router the changes are commited

        return workflow

    @staticmethod
    def update_config(db: Session, id: UUID, schema: WorkflowSchema) -> Workflow:
        workflow = db.query(Workflow).filter(Workflow.id == id).first()

        if workflow:
            ui_metadata = schema.ui_metadata.model_dump()
            workflow.config = schema.execution_config.model_dump()

            if ui_metadata is not None:
                workflow.ui_metadata = ui_metadata

            # we use flush because workflow and deployment services are sequantially dependent
            db.flush()  # in the workflow router the changes are commited

        return workflow

    @staticmethod
    def get_by_user_id(db: Session, id: UUID) -> List[Workflow]:
        return db.query(Workflow).filter(Workflow.user_id == id).all()

    @staticmethod
    def get_by_id(db: Session, id: UUID) -> Optional[Workflow]:
        return db.query(Workflow).filter(Workflow.id == id).first()

    @staticmethod
    def delete_by_id(db: Session, id: UUID) -> None:
        db.query(Workflow).filter(Workflow.id == id).delete(synchronize_session="fetch")
