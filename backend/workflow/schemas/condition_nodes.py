from typing import Annotated, Any, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field


class ConditionRule(BaseModel):
    variable: str = Field(..., description="e.g., '{{trigger_1.subject}}'")
    operator: Literal["equals", "contains", "exists", "greater_than"]
    value: Any


class IfConditionConfig(BaseModel):
    rules: List[ConditionRule]
    match_type: Literal["ANY", "ALL"] = "ALL"


class IfCondition(BaseModel):
    type: Literal["if_condition"]
    config: IfConditionConfig

    model_config = ConfigDict(
        json_schema_extra={"category": "Logic", "icon": "lucide-split"}
    )


Condition = Annotated[
    Union[IfCondition],
    Field(discriminator="type"),
]
