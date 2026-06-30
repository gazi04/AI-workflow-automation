import secrets
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from workflow.models.workflow import Workflow
from workflow.schemas import WorkflowSchema


class WorkflowService:
    @staticmethod
    def schema_has_webhook_trigger(schema: WorkflowSchema) -> bool:
        """True if any start node of the workflow is a `webhook` trigger."""
        config = schema.execution_config
        for node_id in config.start_node_ids:
            node = config.nodes.get(node_id)
            if node and node.type == "trigger" and node.config.type == "webhook":
                return True
        return False

    @staticmethod
    def generate_webhook_secret() -> str:
        """Random URL-safe secret used as the webhook trigger credential."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def create(
        db: Session,
        workflow_id: UUID,
        user_id: UUID,
        schema: WorkflowSchema,
        webhook_secret: Optional[str] = None,
    ) -> Workflow:
        new_workflow = Workflow(
            id=workflow_id,
            user_id=user_id,
            name=schema.name,
            description=schema.description,
            config=schema.execution_config.model_dump(),
            ui_metadata=schema.ui_metadata.model_dump() if schema.ui_metadata else {},
            version=1,
            webhook_secret=webhook_secret,
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
            ui_metadata = (
                schema.ui_metadata.model_dump() if schema.ui_metadata else None
            )
            workflow.config = schema.execution_config.model_dump()

            if ui_metadata is not None:
                workflow.ui_metadata = ui_metadata

            # Backfill a secret when a webhook trigger is added to an existing
            # workflow that never had one, so it gets a usable webhook URL.
            if (
                not workflow.webhook_secret
                and WorkflowService.schema_has_webhook_trigger(schema)
            ):
                workflow.webhook_secret = WorkflowService.generate_webhook_secret()

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
    def get_by_id_and_user(db: Session, id: UUID, user_id: UUID) -> Optional[Workflow]:
        return (
            db.query(Workflow)
            .filter(Workflow.id == id, Workflow.user_id == user_id)
            .first()
        )

    @staticmethod
    def delete_by_id(db: Session, id: UUID) -> None:
        db.query(Workflow).filter(Workflow.id == id).delete(synchronize_session="fetch")
