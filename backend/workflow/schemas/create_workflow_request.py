from pydantic import BaseModel, Field
from typing import Optional
from .workflow_definition import WorkflowDefinition

class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., description="The name of the workflow")
    description: str = Field(..., description="A short description of the workflow")
    workflow_definition: WorkflowDefinition
