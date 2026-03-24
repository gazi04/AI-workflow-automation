from typing import Optional
from pydantic import BaseModel, Field


class Edge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = Field(
        default=None,
        description="Used for Condition Nodes to route logic (e.g., 'true_path', 'false_path')",
    )
    targetHandle: Optional[str] = None
