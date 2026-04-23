from typing import Any, Dict, Optional
from pydantic import BaseModel

from workflow.schemas import WorkflowDefinition


class UserRequest(BaseModel):
    text: str
    current_workflow: Optional[Dict[str, Any]]
