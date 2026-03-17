from pydantic import BaseModel
from typing import Any, List


class FieldDefinition(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: Any = None
    description: str = ""


class NodeDefinition(BaseModel):
    type: str
    category: str
    label: str
    icon: str
    description: str
    fields: List[FieldDefinition]


class WorkflowCatalog(BaseModel):
    triggers: List[NodeDefinition]
    actions: List[NodeDefinition]
