from pydantic import BaseModel, Field
from .trigger_type import TriggerType


class Trigger(BaseModel):
    type: TriggerType = Field(..., description="The event that starts the workflow")
    config: dict = Field(
        ...,
        description="The configuration needed for this trigger, like sender's email, sheet ID, etc.",
    )
