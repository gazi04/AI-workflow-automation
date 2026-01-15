from pydantic import BaseModel, Field
from .action_type import ActionType


class Action(BaseModel):
    type: ActionType = Field(..., description="The type of action to perform")
    config: dict = Field(
        ...,
        description="The configuration needed for this action, like channel name, email address, etc.",
    )
