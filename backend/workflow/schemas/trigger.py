from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Literal, Optional, Union, Annotated


class ManualConfig(BaseModel):
    description: str = "Triggered manually via the UI"


class EmailReceivedConfig(BaseModel):
    from_email: Optional[EmailStr] = Field(None, alias="from")
    subject_contains: Optional[str] = None


class NewSheetRowConfig(BaseModel):
    spreadsheet_id: str


class ScheduleConfig(BaseModel):
    cron: str = Field(..., json_schema_extra={"widget": "cron", "example": "0 9 * * *"})
    description: str = "Runs on a schedule"


class WebhookConfig(BaseModel):
    description: str = "Triggered by an HTTP request"


class ManualTrigger(BaseModel):
    type: Literal["manual"]
    config: ManualConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "General",
            "icon": "lucide-hand",
            "outputs": ["description"],
        }
    )


class EmailReceivedTrigger(BaseModel):
    type: Literal["email_received"]
    config: EmailReceivedConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Communication",
            "icon": "lucide-mail",
            "outputs": ["from", "subject", "body", "id", "thread_id"],
        }
    )


class NewSheetRowTrigger(BaseModel):
    type: Literal["new_sheet_row"]
    config: NewSheetRowConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Data",
            "icon": "lucide-file-spreadsheet",
            "outputs": ["spreadsheet_id", "row_data"],
        }
    )


class ScheduleTrigger(BaseModel):
    type: Literal["schedule"]
    config: ScheduleConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "General",
            "icon": "lucide-calendar",
            "outputs": ["timestamp"],
        }
    )


class WebhookTrigger(BaseModel):
    type: Literal["webhook"]
    config: WebhookConfig

    model_config = ConfigDict(
        json_schema_extra={
            "category": "Developer",
            "icon": "lucide-webhook",
            "outputs": ["body", "headers", "query"],
        }
    )


Trigger = Annotated[
    Union[
        EmailReceivedTrigger,
        ManualTrigger,
        NewSheetRowTrigger,
        ScheduleTrigger,
        WebhookTrigger,
    ],
    Field(discriminator="type"),
]
