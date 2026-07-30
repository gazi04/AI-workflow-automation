from typing import Optional
from pydantic import BaseModel, Field


class Edge(BaseModel):
    id: str
    source: str
    target: str
    # ♻️ todo: Refactor the sourceHandle, use Literal or Enum for type safety and type hinting
    sourceHandle: Optional[str] = Field(
        default=None,
        description="Used for Condition Nodes to route logic (e.g., 'true_path', 'false_path')",
    )
    targetHandle: Optional[str] = None
