from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .workflow_schema import WorkflowSchema


class UpdateWorkflowRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deployment_id: UUID = Field(..., description="The Prefect Deployment ID")
    workflow_schema: WorkflowSchema = Field(
        ..., alias="schema", description="New configuration/parameters to merge"
    )
