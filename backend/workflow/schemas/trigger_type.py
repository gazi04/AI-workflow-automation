from enum import Enum


class TriggerType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    NEW_SHEET_ROW = "new_sheet_row"
    SCHEDULE = "schedule"

