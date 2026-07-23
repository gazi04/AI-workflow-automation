import base64
from email.message import Message
from email.utils import parseaddr
from typing import Any
from uuid import UUID
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.exc import IntegrityError

from core.database import db_session
from core.setup_logging import setup_logger
from gmail.schemas.message import GmailMessage, GmailMessagePart
from orchestration.services.deployment_service import DeploymentService
from processed_messages.services import ProcessedMessageService
from workflow.schemas import WorkflowExecutionConfig
from workflow.services.workflow_service import WorkflowService


class DeploymentTriggerError(Exception):
    """Raised when one or more deployment triggers failed during a sync pass.

    Propagated out of ``fetch_and_process`` so the drain loop in
    ``GmailService.handle_gmail_update`` withholds the baseline advance and the
    next notification re-drains and retries the failed message(s).
    """


class GmailHistoryProcessor:
    """
    Helper class to manage the lifecycle of the Gmail service
    and shared state for a single sync job.
    """

    def __init__(self, creds: Credentials, user_id: UUID):
        self.creds = creds
        self.user_id = user_id
        self.service: Any = None

    async def __aenter__(self):
        self.service = build("gmail", "v1", credentials=self.creds)
        self.logger = setup_logger("Gmail History Processor")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.service:
            self.service.close()

    async def fetch_and_process(self, start_history_id: str) -> None:
        unique_message_ids: set[str] = set()
        page_token = None

        # Batch-level flag set by _process_single_message when a deployment
        # trigger fails. A failed trigger must not advance the sync baseline, so
        # we raise after the loop to force the drain loop to retry next pass.
        self._trigger_failed = False

        # history.list is paged; loop until there is no nextPageToken so messages
        # beyond the first page (busy mailbox / after downtime) aren't dropped.
        while True:
            history_response = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    pageToken=page_token,
                )
                .execute()
            )
            self._collect_message_ids(history_response, unique_message_ids)

            page_token = history_response.get("nextPageToken")
            if not page_token:
                break

        active_workflows = None
        if unique_message_ids:
            async with db_session() as db:
                active_workflows = await self._load_active_workflows(db)

        for message_id in unique_message_ids:
            await self._process_single_message(message_id, active_workflows)

        if self._trigger_failed:
            raise DeploymentTriggerError(
                "One or more deployment triggers failed; baseline withheld for retry."
            )

    def _collect_message_ids(self, history_response, sink: set[str]) -> None:
        for history_record in history_response.get("history", []):
            if "messagesAdded" not in history_record:
                continue

            for message_item in history_record["messagesAdded"]:
                message_id = message_item["message"]["id"]
                sink.add(message_id)

    async def _load_active_workflows(self, db):
        workflows = await WorkflowService.get_by_user_id(db, self.user_id)
        active = []
        for workflow in workflows:
            if not workflow.is_active:
                continue

            workflow_config = WorkflowExecutionConfig.model_validate(workflow.config)
            active.append((workflow, workflow_config))

        return active

    async def _process_single_message(self, message_id: str, active_workflows=None):
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
                "subject": next(
                    (h.value for h in headers if h.name.lower() == "subject"), ""
                ),
                "from": next(
                    (h.value for h in headers if h.name.lower() == "from"), ""
                ),
                "snippet": message.snippet,
                "header_message_id": next(
                    (h.value for h in headers if h.name.lower() == "message-id"), ""
                ),
                "references": next(
                    (h.value for h in headers if h.name.lower() == "references"), ""
                ),
                "body": email_body or message.snippet,
            }

            email_from = email_data["from"].lower()
            email_subject = email_data["subject"].lower()

            async with db_session() as db:
                workflows = active_workflows
                if workflows is None:
                    workflows = await self._load_active_workflows(db)

                for workflow, workflow_config in workflows:
                    start_node_ids = workflow_config.start_node_ids
                    nodes = workflow_config.nodes

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
                            if trigger_from:
                                # Match the sender's address exactly, not as a
                                # substring — otherwise a from_email of "o.com"
                                # matches almost anything. parseaddr pulls the
                                # bare address out of a "Name <addr>" header.
                                _, sender_addr = parseaddr(email_from)
                                _, trigger_addr = parseaddr(trigger_from)
                                trigger_addr = trigger_addr or trigger_from
                                if sender_addr != trigger_addr:
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
                        await ProcessedMessageService.get_by_message_id_and_workflow_id(
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

                    # Trigger first; only mark processed once the deployment is
                    # successfully scheduled. On failure, flag the batch and move
                    # on so the baseline is withheld and this message is retried.
                    try:
                        await DeploymentService.run(workflow.id, trigger_context)
                    except Exception as e:
                        self.logger.error(
                            f"Failed to trigger deployment for workflow {workflow.id}: {e}"
                        )
                        self._trigger_failed = True
                        continue

                    try:
                        await ProcessedMessageService.create(
                            db, email_data["message_id"], workflow.id
                        )
                    except IntegrityError:
                        # Concurrent insert or a re-drain raced us — the message is
                        # already recorded for this workflow, so treat as handled.
                        await db.rollback()
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(
                    f"Message {message_id} not found (likely deleted). Skipping."
                )
                return
            self.logger.error(f"Gmail API HttpError: {e}")
        except Exception as e:
            self.logger.error(f"Unhandled error occurred: {e}")

    @staticmethod
    def _charset_for(part: GmailMessagePart) -> str:
        """Read the declared charset from the part's Content-Type header.

        Falls back to utf-8 when absent so non-UTF-8 bodies (latin-1,
        windows-1252) decode correctly instead of being mangled.
        """
        ct = next(
            (h.value for h in part.headers if h.name.lower() == "content-type"),
            "",
        )
        msg = Message()
        msg["content-type"] = ct
        return msg.get_content_charset() or "utf-8"

    def _decode_part(self, part: GmailMessagePart) -> str:
        """Decode a part's base64 body using its declared charset."""
        raw = base64.urlsafe_b64decode(part.body.data)  # type: ignore[union-attr]
        try:
            return raw.decode(self._charset_for(part), errors="replace")
        except LookupError:
            # Unknown/invalid codec name — fall back to lossy utf-8.
            return raw.decode("utf-8", errors="replace")

    def _get_email_body(self, payload: GmailMessagePart) -> str:
        """
        Recursively extracts the plain text body from the email payload.
        """
        if payload.body and payload.body.data:
            if payload.mime_type == "text/plain":
                return self._decode_part(payload)

        for part in payload.parts:
            if part.mime_type == "text/plain" and part.body and part.body.data:
                return self._decode_part(part)

            if part.mime_type.startswith("multipart"):
                body = self._get_email_body(part)
                if body:
                    return body

        return ""
