from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from gmail.schemas.colors import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_TEXT_COLOR,
    GmailBackgroundHex,
    GmailTextHex,
    clamp_background_color,
    clamp_text_color,
)


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
    backgroundColor: GmailBackgroundHex = Field(
        default=DEFAULT_BACKGROUND_COLOR,
        description="The background color hex string (e.g., #000000)",
    )
    textColor: GmailTextHex = Field(
        default=DEFAULT_TEXT_COLOR,
        description="The text color hex string (e.g., #ffffff)",
    )

    # mode="before" is load-bearing: an after-validator runs *behind* the Literal
    # check, so an off-palette colour would raise before it could be clamped.
    @field_validator("backgroundColor", mode="before")
    @classmethod
    def check_background_color_palette(cls, v: Any) -> GmailBackgroundHex:
        return clamp_background_color(v)

    @field_validator("textColor", mode="before")
    @classmethod
    def check_text_color_palette(cls, v: Any) -> GmailTextHex:
        return clamp_text_color(v)


class GmailLabel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    labelListVisibility: Optional[LabelListVisibility] = None
    messageListVisibility: Optional[MessageListVisibility] = None
    type: Optional[LabelType] = None
    color: Optional[LabelColor] = Field(default_factory=LabelColor)
