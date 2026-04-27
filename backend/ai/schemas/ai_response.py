from typing import Optional
from pydantic import BaseModel
from workflow.schemas import WorkflowSchema


class AIResponse(BaseModel):
    success: bool
    data: Optional[WorkflowSchema] = None
    error: Optional[str] = None
