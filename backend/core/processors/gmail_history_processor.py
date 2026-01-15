from uuid import UUID
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Dict, Any

from core.database import db_session
from core.setup_logging import setup_logger
from orchestration.services.deployment_service import DeploymentService
from processed_messages.services.processed_message_service import (
    ProcessedMessageService,
)
from workflow.services.workflow_service import WorkflowService


class GmailHistoryProcessor:
    """
    Helper class to manage the lifecycle of the Gmail service
    and shared state for a single sync job.
    """

    def __init__(self, creds: Credentials, user_id: UUID):
        self.creds = creds
        self.user_id = user_id
        self.service = None

    def __enter__(self):
        self.service = build("gmail", "v1", credentials=self.creds)
        self.logger = setup_logger("Gmail History Processor")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.service:
            self.service.close()

    async def fetch_and_process(self, start_history_id: str) -> None:
        history_response = (
            self.service.users()
            .history()
            .list(userId="me", startHistoryId=start_history_id)
            .execute()
        )
        await self._filter_notifications(history_response)

    async def _filter_notifications(self, history_response: Dict[str, Any]):
        unique_message_ids = set()

        for history_record in history_response.get("history", []):
            if "messagesAdded" not in history_record:
                continue

            for message_item in history_record["messagesAdded"]:
                message_id = message_item["message"]["id"]
                unique_message_ids.add(message_id)
                # await self._process_single_message(message_id)

        if not unique_message_ids:
            self.logger.info("No new messages found in this sync.")
            return

        for message_id in unique_message_ids:
            await self._process_single_message(message_id)

    async def _process_single_message(self, message_id: str):
        try:
            full_message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id)
                .execute()
            )

            labels = full_message.get("labelIds", [])

            if "INBOX" not in labels or "UNREAD" not in labels:
                self.logger.debug(f"Skipping message {message_id}. Labels are {labels}")
                return

            payload = full_message.get("payload", {})
            headers = payload.get("headers", [])

            email_data = {
                "thread_id": full_message.get("threadId", ""),
                "message_id": message_id,
                "subject": next(
                    (h["value"] for h in headers if h["name"] == "Subject"), ""
                ),
                "from": next((h["value"] for h in headers if h["name"] == "From"), ""),
                "snippet": full_message.get("snippet", ""),
                "header_message_id": next(
                    (h["value"] for h in headers if h["name"].lower() == "message-id"),
                    "",
                ),
                "references": next(
                    (h["value"] for h in headers if h["name"].lower() == "references"),
                    "",
                ),
            }

            with db_session() as db:
                # ⚡ todo: improve performance by caching the workflows
                workflows = await WorkflowService.get_by_user_id(db, self.user_id)

                for workflow in workflows:
                    if not workflow.is_active:
                        self.logger.info(
                            f"Skipping workflow {workflow.id} because it's inactive"
                        )
                        continue

                    config = workflow.config or {}
                    trigger = config.get("trigger")

                    if not trigger or trigger.get("type") != "email_received":
                        continue

                    trigger_config = trigger.get("config", {})

                    trigger_from = trigger_config.get("from", "").strip().lower()
                    email_from = email_data["from"].lower()

                    if trigger_from and trigger_from not in email_from:
                        continue

                    exists_processed_message = (
                        await ProcessedMessageService.get_by_message_id_and_workflow_id(
                            db, email_data["message_id"], workflow.id
                        )
                    )

                    if exists_processed_message:
                        self.logger.info(
                            f"Skipping duplicated: Workflow {workflow.id} already ran for message {message_id}"
                        )
                        continue

                    trigger_subject = (
                        trigger_config.get("subject_contains", "").strip().lower()
                    )
                    email_subject = email_data["subject"].lower()

                    if trigger_subject and trigger_subject not in email_subject:
                        continue

                    self.logger.info(
                        f"✅ MATCH FOUND! Workflow ID: {workflow.id}\n"
                        f"   Reason: Matched Trigger Rules\n"
                        f"   Email Subject: {email_data['subject']}\n"
                        f"   Email From: {email_data['from']}"
                    )

                    trigger_context = {
                        "trigger_context": {"original_email": email_data}
                    }

                    await ProcessedMessageService.create(
                        db, email_data["message_id"], workflow.id
                    )
                    await DeploymentService.run(workflow.id, trigger_context)
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(
                    f"Message {message_id} not found (likely deleted). Skipping."
                )
                return
            self.logger.error(f"Unhandled http error occurred: \n{e}")
