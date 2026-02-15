from pydantic import BaseModel, Field, EmailStr
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

class SendEmailAction(BaseModel):
    type: Literal["send_email"]
    config: SendEmailConfig

class ReplyEmailAction(BaseModel):
    type: Literal["reply_email"]
    config: ReplyEmailConfig

class LabelEmailAction(BaseModel):
    type: Literal["label_email"]
    config: LabelEmailConfig

class SmartDraftAction(BaseModel):
    type: Literal["smart_draft"]
    config: SmartDraftConfig

class CreateDocumentAction(BaseModel):
    type: Literal["create_document"]
    config: CreateDocumentConfig

Action = Annotated[
    Union[
        SendSlackMessageAction,
        SendEmailAction,
        ReplyEmailAction,
        LabelEmailAction,
        SmartDraftAction,
        CreateDocumentAction,
    ],
    Field(discriminator="type")
]
