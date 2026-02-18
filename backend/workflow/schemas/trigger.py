from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Union, Annotated


class EmailReceivedConfig(BaseModel):
    from_email: EmailStr = Field(..., alias="from")
    subject_contains: str = ""


class NewSheetRowConfig(BaseModel):
    spreadsheet_id: str


class ScheduleConfig(BaseModel):
    cron: str = Field(..., example="0 9 * * *")
    description: str


class EmailReceivedTrigger(BaseModel):
    type: Literal["email_received"]
    config: EmailReceivedConfig


class NewSheetRowTrigger(BaseModel):
    type: Literal["new_sheet_row"]
    config: NewSheetRowConfig


class ScheduleTrigger(BaseModel):
    type: Literal["schedule"]
    config: ScheduleConfig


Trigger = Annotated[
    Union[EmailReceivedTrigger, NewSheetRowTrigger, ScheduleTrigger],
    Field(discriminator="type"),
]
