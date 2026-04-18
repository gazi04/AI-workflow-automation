from enum import Enum
from typing import Annotated, Any, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field


class ConditionOperators(str, Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    EXISTS = "exists"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


class ConditionRule(BaseModel):
    variable: str = Field(..., description="e.g., '{{trigger_1.subject}}'")
    operator: ConditionOperators
    value: Any


class IfConditionConfig(BaseModel):
    rules: List[ConditionRule] = Field(..., json_schema_extra={"widget": "rule_builder"})
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
