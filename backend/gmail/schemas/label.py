from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from utils.gmail_colors import validate_background_color, validate_text_color

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
    backgroundColor: str = Field(..., description="The background color hex string (e.g., #000000)")
    textColor: str = Field(..., description="The text color hex string (e.g., #ffffff)")

    @field_validator('backgroundColor')
    @classmethod
    def check_background_color_palette(cls, v: str) -> Optional[str]:
        return validate_background_color(v)

    @field_validator('textColor')
    @classmethod
    def check_text_color_palette(cls, v: str) -> Optional[str]:
        return validate_text_color(v)

class GmailLabel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    labelListVisibility: Optional[LabelListVisibility] = None
    messageListVisibility: Optional[MessageListVisibility] = None
    type: Optional[LabelType] = None
    color: Optional[LabelColor] = None
