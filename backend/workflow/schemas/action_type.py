from enum import Enum

class ActionType(str, Enum):
    SEND_SLACK_MESSAGE = "send_slack_message"
    SEND_EMAIL = "send_email"
    CREATE_DOCUMENT = "create_document"
