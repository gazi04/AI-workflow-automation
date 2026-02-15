from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from .workflow_definition import WorkflowDefinition

class UpdateWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    config: WorkflowDefinition = Field(
        ..., description="New configuration/parameters to merge"
    )
