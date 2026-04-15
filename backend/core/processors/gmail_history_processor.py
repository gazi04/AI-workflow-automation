import base64
from uuid import UUID
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Dict, Any

from core.database import db_session
from core.setup_logging import setup_logger
from gmail.schemas.message import GmailMessage, GmailMessagePart
from orchestration.services.deployment_service import DeploymentService
from processed_messages.services import ProcessedMessageService
from workflow.schemas.workflow_definition import WorkflowDefinition
from workflow.services.workflow_service import WorkflowService

import anyio


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

    def fetch_and_process(self, start_history_id: str) -> None:
        history_response = (
            self.service.users()
            .history()
            .list(userId="me", startHistoryId=start_history_id)
            .execute()
        )
        self._filter_notifications(history_response)

    def _filter_notifications(self, history_response: Dict[str, Any]):
        unique_message_ids = set()

        for history_record in history_response.get("history", []):
            if "messagesAdded" not in history_record:
                continue

            for message_item in history_record["messagesAdded"]:
                message_id = message_item["message"]["id"]
                unique_message_ids.add(message_id)

        if not unique_message_ids:
            return

        for message_id in unique_message_ids:
            self._process_single_message(message_id)

    def _process_single_message(self, message_id: str):
        try:
            raw_message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id)
                .execute()
            )

            message = GmailMessage.model_validate(raw_message)

            labels = message.label_ids

            if "INBOX" not in labels or "SPAM" in labels or "TRASH" in labels:
                return

            payload = message.payload
            headers = payload.headers
            email_body = self._get_email_body(payload)

            email_data = {
                "message_id": message_id,
                "thread_id": message.thread_id,
                "subject": next((h.value for h in headers if h.name.lower() == "subject"), ""),
                "from": next((h.value for h in headers if h.name.lower() == "from"), ""),
                "snippet": message.snippet,
                "header_message_id": next((h.value for h in headers if h.name.lower() == "message-id"), ""),
                "references": next((h.value for h in headers if h.name.lower() == "references"), ""),
                "body": email_body or message.snippet
            }

            email_from = email_data["from"].lower()
            email_subject = email_data["subject"].lower()

            with db_session() as db:
                # ⚡ todo: improve performance by caching the workflows
                workflows = WorkflowService.get_by_user_id(db, self.user_id)

                active_ids = [w.id for w in workflows if w.is_active]

                for workflow in workflows:
                    if not workflow.is_active:
                        continue

                    workflow_definition = WorkflowDefinition.model_validate(
                        workflow.config
                    )
                    start_node_ids = workflow_definition.start_node_ids
                    nodes = workflow_definition.nodes

                    matched_trigger_node_id = None

                    for node_id in start_node_ids:
                        node = nodes.get(node_id)
                        if not node:
                            continue

                        node_type = node.type
                        node_config = node.config

                        if (
                            node_type == "trigger"
                            and node_config.type == "email_received"
                        ):
                            trigger_from = (
                                (node_config.config.from_email or "").strip().lower()
                            )
                            if trigger_from and trigger_from not in email_from:
                                continue

                            trigger_subject = (
                                (node_config.config.subject_contains or "")
                                .strip()
                                .lower()
                            )
                            if trigger_subject and trigger_subject not in email_subject:
                                continue

                            matched_trigger_node_id = node_id
                            break

                    if not matched_trigger_node_id:
                        continue

                    exists_processed_message = (
                        ProcessedMessageService.get_by_message_id_and_workflow_id(
                            db, email_data["message_id"], workflow.id
                        )
                    )

                    if exists_processed_message:
                        continue

                    # We pass the context directly to the deployment run
                    trigger_context = {
                        "trigger_context": {
                            "original_email": email_data,
                            "matched_trigger_node_id": matched_trigger_node_id,
                        }
                    }

                    ProcessedMessageService.create(
                        db, email_data["message_id"], workflow.id
                    )

                    try:
                        anyio.from_thread.run(
                            DeploymentService.run, workflow.id, trigger_context
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to trigger deployment for workflow {workflow.id}: {e}"
                        )
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(
                    f"Message {message_id} not found (likely deleted). Skipping."
                )
                return
            self.logger.error(f"Gmail API HttpError: {e}")
        except Exception as e:
            self.logger.error(f"Unhandled error occurred: {e}")

    def _get_email_body(self, payload: GmailMessagePart) -> str:
        """
        Recursively extracts the plain text body from the email payload.
        """
        if payload.body and payload.body.data:
            if payload.mime_type == "text/plain":
                return base64.urlsafe_b64decode(payload.body.data).decode("utf-8")

        for part in payload.parts:
            if part.mime_type == "text/plain" and part.body and part.body.data:
                return base64.urlsafe_b64decode(part.body.data).decode("utf-8")

            if part.mime_type.startswith("multipart"):
                body = self._get_email_body(part)
                if body:
                    return body

        return ""
