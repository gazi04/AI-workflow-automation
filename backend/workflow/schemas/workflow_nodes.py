from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from workflow.schemas.action import (
    CreateDocumentAction,
    LabelEmailAction,
    ReplyEmailAction,
    SendEmailAction,
    SendSlackMessageAction,
    SmartDraftAction,
)
from workflow.schemas.condition_nodes import IfCondition
from workflow.schemas.trigger import (
    EmailReceivedTrigger,
    ManualTrigger,
    NewSheetRowTrigger,
    ScheduleTrigger,
)


NodeConfig = Annotated[
    Union[
        EmailReceivedTrigger,
        ManualTrigger,
        NewSheetRowTrigger,
        ScheduleTrigger,
        SendSlackMessageAction,
        SendEmailAction,
        ReplyEmailAction,
        LabelEmailAction,
        SmartDraftAction,
        CreateDocumentAction,
        IfCondition,
    ],
    Field(discriminator="type"),
]


class WorkflowNode(BaseModel):
    id: str
    name: Optional[str] = None
    type: Literal["trigger", "action", "condition"]
    config: NodeConfig
