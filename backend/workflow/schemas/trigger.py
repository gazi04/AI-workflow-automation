from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator
from typing import Literal, Optional, Union, Annotated


class ManualConfig(BaseModel):
    description: str = "Triggered manually via the UI"


class EmailReceivedConfig(BaseModel):
    from_email: Optional[EmailStr] = Field(None, alias="from")
    subject_contains: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_is_required(self) -> "EmailReceivedConfig":
        if self.from_email is None and self.subject_contains is None:
            raise ValueError("At least one of the attributes should be provided.")
        return self


class NewSheetRowConfig(BaseModel):
    spreadsheet_id: str


class ScheduleConfig(BaseModel):
    cron: str = Field(..., json_schema_extra={"example": "0 9 * * *"})
    description: str


class ManualTrigger(BaseModel):
    type: Literal["manual"]
    config: ManualConfig

    model_config = ConfigDict(
        json_schema_extra={"category": "General", "icon": "lucide-hand"}
    )


class EmailReceivedTrigger(BaseModel):
    type: Literal["email_received"]
    config: EmailReceivedConfig

    model_config = ConfigDict(
        json_schema_extra={"category": "Communication", "icon": "lucide-mail"}
    )


class NewSheetRowTrigger(BaseModel):
    type: Literal["new_sheet_row"]
    config: NewSheetRowConfig

    model_config = ConfigDict(
        json_schema_extra={"category": "Data", "icon": "lucide-file-spreadsheet"}
    )


class ScheduleTrigger(BaseModel):
    type: Literal["schedule"]
    config: ScheduleConfig

    model_config = ConfigDict(
        json_schema_extra={"category": "General", "icon": "lucide-calendar"}
    )


Trigger = Annotated[
    Union[EmailReceivedTrigger, ManualTrigger, NewSheetRowTrigger, ScheduleTrigger],
    Field(discriminator="type"),
]
