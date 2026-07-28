from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from typing import Any, Literal, Union, Annotated

from gmail.schemas.colors import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_TEXT_COLOR,
    GmailBackgroundHex,
    GmailTextHex,
    clamp_background_color,
    clamp_text_color,
)
from gmail.schemas.label import GmailLabel, LabelColor


class SendSlackMessageConfig(BaseModel):
    channel: str = Field(..., description="Channel name or ID (e.g., #general)")
    message: str


class SendEmailConfig(BaseModel):
    to: EmailStr
    subject: str
    body: str


class ReplyEmailConfig(BaseModel):
    body: str


class LabelEmailConfig(BaseModel):
    label_name: str = Field(..., description="The name of the label (e.g., 'OFFERS')")
    background_color: GmailBackgroundHex = DEFAULT_BACKGROUND_COLOR
    text_color: GmailTextHex = DEFAULT_TEXT_COLOR

    # Clamp instead of reject: workflows saved before the palette was enforced must keep
    # loading and running (they fall back to the default) rather than 422 on read.
    @field_validator("background_color", mode="before")
    @classmethod
    def _clamp_background_color(cls, v: Any) -> GmailBackgroundHex:
        return clamp_background_color(v)

    @field_validator("text_color", mode="before")
    @classmethod
    def _clamp_text_color(cls, v: Any) -> GmailTextHex:
        return clamp_text_color(v)

    @property
    def label_info(self) -> GmailLabel:
        """Backward compatibility for the execution engine."""
        return GmailLabel(
            name=self.label_name,
            color=LabelColor(
                backgroundColor=self.background_color,
                textColor=self.text_color,
            ),
        )


class SmartDraftConfig(BaseModel):
    user_prompt: str


class CreateDocumentConfig(BaseModel):
    title: str
    content: str


class SendSlackMessageAction(BaseModel):
    type: Literal["send_slack_message"]
    config: SendSlackMessageConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Communication",
            "icon": "lucide-slack",
            "outputs": ["status"],
            "status": "coming_soon",
        }
    )


class SendEmailAction(BaseModel):
    type: Literal["send_email"]
    config: SendEmailConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Communication",
            "icon": "lucide-send",
            "outputs": ["id"],
        }
    )


class ReplyEmailAction(BaseModel):
    type: Literal["reply_email"]
    config: ReplyEmailConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Communication",
            "icon": "lucide-reply",
            "outputs": ["id"],
        }
    )


class LabelEmailAction(BaseModel):
    type: Literal["label_email"]
    config: LabelEmailConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Google",
            "icon": "lucide-tag",
            "outputs": ["labels"],
        }
    )


class SmartDraftAction(BaseModel):
    type: Literal["smart_draft"]
    config: SmartDraftConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "AI",
            "icon": "lucide-sparkles",
            "outputs": ["id", "body"],
        }
    )


class CreateDocumentAction(BaseModel):
    type: Literal["create_document"]
    config: CreateDocumentConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Google",
            "icon": "lucide-file-text",
            "outputs": ["document_id", "title"],
            "status": "coming_soon",
        }
    )


Action = Annotated[
    Union[
        SendSlackMessageAction,
        SendEmailAction,
        ReplyEmailAction,
        LabelEmailAction,
        SmartDraftAction,
        CreateDocumentAction,
    ],
    Field(discriminator="type"),
]
