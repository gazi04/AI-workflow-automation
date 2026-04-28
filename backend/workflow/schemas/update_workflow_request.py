from uuid import UUID
from pydantic import BaseModel, Field
from .workflow_schema import WorkflowSchema


class UpdateWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    schema: WorkflowSchema = Field(
        ..., description="New configuration/parameters to merge"
    )
