from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Dict, Any

from core.setup_logging import setup_logger


class GmailHistoryProcessor:
    """
    Helper class to manage the lifecycle of the Gmail service
    and shared state for a single sync job.
    """
    def __init__(self, creds):
        self.creds = creds
        self.service = None

    def __enter__(self):
        self.service = build("gmail", "v1", credentials=self.creds)
        self.logger = setup_logger("Gmail History Processor")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.service:
            self.service.close()

    def fetch_and_process(self, start_history_id: str) -> None:
        history_response = (
            self.service.users()
            .history()
            .list(userId="me", startHistoryId=start_history_id)
            .execute()
        )
        self._filter_notifications(history_response)

    def _filter_notifications(self, history_response: Dict[str, Any]):
        for history_record in history_response.get("history", []):
            if "messagesAdded" not in history_record:
                continue

            for message_item in history_record["messagesAdded"]:
                message_id = message_item["message"]["id"]
                self._process_single_message(message_id)

    def _process_single_message(self, message_id: str):
        try:
            full_message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id)
                .execute()
            )

            labels = full_message.get("labelIds", [])

            if "INBOX" in labels and "UNREAD" in labels:
                self.logger.info(f"New unread message: {full_message['snippet']}")
            else: 
                self.logger.debug(f"Skipping message {message_id}. Labels are {labels}")
            # 🟢 todo: triggering prefect deployment logic here
            # logger.info(f"Triggering workflow for message: {message_id}")

        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"Message {message_id} not found (likely deleted). Skipping.")
                return
            self.logger.error(f"Unhandled http error occurred: \n{e}")
