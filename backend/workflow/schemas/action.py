from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Literal, Union, Annotated

from gmail.schemas.label import GmailLabel


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
    label_info: GmailLabel


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
