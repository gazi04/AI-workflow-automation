from uuid import UUID
from pydantic import BaseModel, Field


class RunWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    config: dict = Field(default_factory=dict, description="Workflow parameters")
