from pydantic import BaseModel, Field
from typing import List, Optional
from .trigger import Trigger
from .action import Action
from .ui_metadata_workflow import UIMetadata


class WorkflowDefinition(BaseModel):
    name: str = Field(..., description="A concise, descriptive name for this workflow")
    description: str = Field(
        ..., description="A one-sentence summary of the workflow's purpose"
    )
    trigger: Trigger
    actions: List[Action]
    ui_metadata: Optional[UIMetadata] = None
