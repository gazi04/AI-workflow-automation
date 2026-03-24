from typing import Any, List, Literal
from pydantic import BaseModel, Field


class ConditionRule(BaseModel):
    variable: str = Field(..., description="e.g., '{{trigger_1.subject}}'")
    operator: Literal["equals", "contains", "exists", "greater_than"]
    value: Any


class IfConditionConfig(BaseModel):
    type: Literal["if_condition"] = "if_condition"
    rules: List[ConditionRule]
    match_type: Literal["ANY", "ALL"] = "ALL"
