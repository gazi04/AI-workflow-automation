from contextlib import contextmanager
from email.message import EmailMessage
from typing import Any, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid import UUID

from auth.services.auth_service import AuthService
from core.database import db_session
from core.setup_logging import setup_logger
from gmail.schemas.label import (
    GmailLabel,
    LabelColor,
    LabelListVisibility,
    LabelType,
    MessageListVisibility,
)
from user.services.user_service import UserService

import base64

logger = setup_logger("Prefect Gmail Task")


class GmailTasks:
    PROVIDER = "google"

    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]

    @staticmethod
    @contextmanager
    def _get_gmail_service(user_id: UUID):
        """
        Private helper to handle DB session, credentials, and service building.
        Uses a context manager to ensure the service is built and closed correctly.
        """
        with db_session() as db:
            creds = AuthService.get_google_credentials(
                db, user_id, GmailTasks.PROVIDER, GmailTasks.DEFAULT_SCOPES
            )
            # Service build as a context manager (supported by google-api-python-client)
            with build("gmail", "v1", credentials=creds) as service:
                yield service, db

    @staticmethod
    def create_draft(user_id: UUID, to: str, subject: str, body: str):
        """
        Create and insert a draft email.
        Print the returned draft's message and id.
        Returns: Draft object, including draft id and message meta data.
        """

        try:
            with GmailTasks._get_gmail_service(user_id) as (service, db):
                user_email = UserService.get_email(db, user_id)

                message = EmailMessage()
                message.set_content(body)

                message["To"] = to
                message["From"] = user_email
                message["Subject"] = subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

                create_message = {"message": {"raw": encoded_message}}

                draft = (
                    service.users()
                    .drafts()
                    .create(userId="me", body=create_message)
                    .execute()
                )

                print(f"Draft id: {draft['id']}\nDraft message: {draft['message']}")
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise error

        return draft

    @staticmethod
    def send_message(user_id: UUID, to: str, subject: str, body: str):
        """
        Create and send an email message
        Print the returned  message id
        Returns: Message object, including message id
        """
        try:
            with GmailTasks._get_gmail_service(user_id) as (service, db):
                user_email = UserService.get_email(db, user_id)

                message = EmailMessage()

                message.set_content(body)

                message["To"] = to
                message["From"] = user_email
                message["Subject"] = subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

                create_message = {"raw": encoded_message}

                send_message = (
                    service.users()
                    .messages()
                    .send(userId="me", body=create_message)
                    .execute()
                )
                print(f"Message Id: {send_message['id']}")
        except HttpError as error:
            print(f"An http error occurred: {error}")
            logger.error(f"Http error occurred: \n {error}")
            raise error
        except Exception as error:
            print(f"An error occurred: {error}")
            logger.error(f"Unhandled error occurred: \n {error}")
            raise error

        return send_message

    @staticmethod
    def reply_email(user_id: UUID, body: str, original_email: Dict[str, Any]):
        """
        Reply to an email with a predefined message.
        original_email contains: subject, from, header_message_id, references, thread_id
        """

        try:
            with GmailTasks._get_gmail_service(user_id) as (service, db):
                message = EmailMessage()
                message.set_content(body)

                # subject should start with Re if it doesn't already
                subject = original_email["subject"]
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"

                message["To"] = original_email["from"]
                message["Subject"] = subject

                message["In-Reply-To"] = original_email["header_message_id"]
                old_refs = original_email["references"]
                message["References"] = (
                    f"{old_refs} {original_email['header_message_id']}".strip()
                )

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

                create_message = {
                    "raw": encoded_message,
                    "threadId": original_email[
                        "thread_id"
                    ],  # Crucial for Gmail UI threading
                }

                return (
                    service.users()
                    .messages()
                    .send(userId="me", body=create_message)
                    .execute()
                )
        except HttpError as error:
            print(f"An http error occurred: {error}")
            logger.error(f"Http error occurred: \n {error}")
            raise error
        except Exception as error:
            print(f"An error occurred: {error}")
            logger.error(f"Unhandled error occurred: \n {error}")
            raise error

    @staticmethod
    def label_mail(
        user_id: UUID,
        label: str,
        backgroundColor: Optional[str],
        textColor: Optional[str],
        original_email: Dict[str, Any],
    ):
        """
        Label emails with an existing label or with a new (non-exsiting) label
        original_email contains: subject, from, header_message_id, references, thread_id
        """

        try:
            with GmailTasks._get_gmail_service(user_id) as (service, db):
                response = service.users().labels().list(userId="me").execute()

                labels = response.get("labels", [])

                label_exists = next((l for l in labels if l["name"] == label), None)

                if not label_exists:
                    logger.info(
                        f"Label {label} doesn't exists, we're creating the label..."
                    )
                    print(f"Label doesn't exists, we're creating the label...")
                    request = {
                        "name": label,
                        "labelListVisibility": LabelListVisibility.LABEL_SHOW,
                        "messageListVisibility": MessageListVisibility.SHOW,
                        "type": LabelType.USER,
                    }

                    request = GmailLabel(**request)

                    if backgroundColor and textColor:
                        color = LabelColor(
                            backgroundColor=backgroundColor, textColor=textColor
                        )
                        request.color = color

                    label_exists = (
                        service.users()
                        .labels()
                        .create(
                            userId="me",
                            body=request.model_dump(mode="json", exclude_none=True),
                        )
                        .execute()
                    )

                    print(f"The label is created with success")

                label_id = label_exists.get("id", None)
                message_id = original_email.get("message_id", None)

                if not message_id or not label_id:
                    raise ValueError(f"Either label id or message id is none.")

                request = {"addLabelIds": [label_id]}

                service.users().messages().modify(
                    userId="me", id=message_id, body=request
                ).execute()

            return labels
        except HttpError as error:
            print(f"An http error occurred: {error}")
            logger.error(f"Http error occurred: \n {error}")
            raise error
        except Exception as error:
            print(f"An error occurred: {error}")
            logger.error(f"Unhandled error: {error}")
            raise error
