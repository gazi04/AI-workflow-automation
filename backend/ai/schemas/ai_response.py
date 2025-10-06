from typing import Optional
from pydantic import BaseModel
from workflow.schemas.workflow_definition import WorkflowDefinition


class AIResponse(BaseModel):
    success: bool
    data: Optional[WorkflowDefinition] = None
    error: Optional[str] = None
