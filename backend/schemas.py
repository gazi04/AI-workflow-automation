from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from enum import Enum


class TriggerType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    NEW_SHEET_ROW = "new_sheet_row"


class ActionType(str, Enum):
    SEND_SLACK_MESSAGE = "send_slack_message"
    SEND_EMAIL = "send_email"
    CREATE_DOCUMENT = "create_document"


class Action(BaseModel):
    type: ActionType = Field(..., description="The type of action to perform")
    config: dict = Field(
        ...,
        description="The configuration needed for this action, like channel name, email address, etc.",
    )


class Trigger(BaseModel):
    type: TriggerType = Field(..., description="The event that starts the workflow")
    config: dict = Field(
        ...,
        description="The configuration needed for this trigger, like sender's email, sheet ID, etc.",
    )


class WorkflowDefinition(BaseModel):
    name: str = Field(..., description="A concise, descriptive name for this workflow")
    description: str = Field(
        ..., description="A one-sentence summary of the workflow's purpose"
    )
    trigger: Trigger
    actions: List[Action]


class UserRequest(BaseModel):
    text: str


class AIResponse(BaseModel):
    success: bool
    data: Optional[WorkflowDefinition] = None
    error: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str
