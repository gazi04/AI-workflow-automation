from uuid import UUID
from pydantic import BaseModel, Field


class DeleteWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")

