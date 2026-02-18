from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class UIMetadata(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    viewport: Optional[Dict[str, Any]] = None
