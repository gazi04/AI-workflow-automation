from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class LabelListVisibility(str, Enum):
    LABEL_SHOW = "labelShow"
    LABEL_SHOW_IF_UNREAD = "labelShowIfUnread"
    LABEL_HIDE = "labelHide"

class MessageListVisibility(str, Enum):
    SHOW = "show"
    HIDE = "hide"

class LabelType(str, Enum):
    SYSTEM = "system"
    USER = "user"

class LabelColor(BaseModel):
    # Gmail only allows specific hex codes. backgroundColor and textColor are required together.
    backgroundColor: str = Field(..., description="The background color hex string (e.g., #000000)")
    textColor: str = Field(..., description="The text color hex string (e.g., #ffffff)")

class GmailLabel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    labelListVisibility: Optional[LabelListVisibility] = None
    messageListVisibility: Optional[MessageListVisibility] = None
    type: Optional[LabelType] = None
    color: Optional[LabelColor] = None
