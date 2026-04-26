from typing import Any, Dict, Optional
from pydantic import BaseModel


class UserRequest(BaseModel):
    text: str
    current_workflow: Optional[Dict[str, Any]]
