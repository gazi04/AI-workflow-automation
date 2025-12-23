from uuid import UUID
from pydantic import BaseModel, Field


class ToggleWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    status: bool = Field(..., description="True to Resume (Active), False to Pause")

