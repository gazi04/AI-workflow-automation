from enum import Enum


class ActionType(str, Enum):
    SEND_SLACK_MESSAGE = "send_slack_message"
    SEND_EMAIL = "send_email"
    REPLY_EMAIL = "reply_email"
    LABEL_EMAIL = "label_email"
    SMART_DRAFT = "smart_draf"
    CREATE_DOCUMENT = "create_document"
