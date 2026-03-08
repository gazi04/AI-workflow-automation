from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Union, Annotated

class ManualConfig(BaseModel):
    description: str = "Triggered manually via the UI"

class EmailReceivedConfig(BaseModel):
    from_email: EmailStr = Field(..., alias="from")
    subject_contains: str = ""


class NewSheetRowConfig(BaseModel):
    spreadsheet_id: str


class ScheduleConfig(BaseModel):
    cron: str = Field(..., json_schema_extra={"example": "0 9 * * *"})
    description: str

class ManualTrigger(BaseModel):
    type: Literal["manual"]
    config: ManualConfig

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
    Union[EmailReceivedTrigger, ManualTrigger, NewSheetRowTrigger, ScheduleTrigger],
    Field(discriminator="type"),
]
