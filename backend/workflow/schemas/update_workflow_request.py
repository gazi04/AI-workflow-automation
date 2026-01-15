from typing import Any, Dict
from uuid import UUID
from pydantic import BaseModel, Field


class UpdateWorkflowRequest(BaseModel):
    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    config: Dict[str, Any] = Field(
        ..., description="New configuration/parameters to merge"
    )
