from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid import UUID
from sqlalchemy.orm import Session

from auth.services.auth_service import AuthService
from core.config_loader import settings

import base64

class GmailService:
    @staticmethod
    async def create_draft(db: Session, user_id: UUID):
        """Create and insert a draft email.
            Print the returned draft's message and id.
            Returns: Draft object, including draft id and message meta data.
        """

        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.compose",
        ]

        creds = AuthService.get_google_credentials(db, user_id, provider, scopes)

        try:
            # ♻️ todo: refactore the service names and use enums
            service = build("gmail", "v1", credentials=creds)

            message = EmailMessage()

            message.set_content("This is automated draft mail")

            message["To"] = "gazmend.halili.st@uni-gjilan.net"
            message["From"] = "gazmendhalili2016@gmail.com"
            message["Subject"] = "Automated draft"

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"message": {"raw": encoded_message}}

            # pylint: disable=E1101
            draft = (
                service.users()
                .drafts()
                .create(userId="me", body=create_message)
                .execute()
            )

            print(f'Draft id: {draft["id"]}\nDraft message: {draft["message"]}')
        except HttpError as error:
            print(f"An error occurred: {error}")
            draft = None

        return draft

    @staticmethod
    async def send_message(db: Session, user_id: UUID):
        """Create and send an email message
        Print the returned  message id
        Returns: Message object, including message id
        """
        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.compose",
        ]

        creds = AuthService.get_google_credentials(db, user_id, provider, scopes)

        try:
            service = build("gmail", "v1", credentials=creds)
            message = EmailMessage()

            message.set_content("This is automated draft mail")

            message["To"] = "gazmend.halili.st@uni-gjilan.net"
            message["From"] = "gazmendhalili2016@gmail.com"
            message["Subject"] = "Sending automated email"

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"raw": encoded_message}
            # pylint: disable=E1101
            send_message = (
                service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            print(f'Message Id: {send_message["id"]}')
        except HttpError as error:
            print(f"An error occurred: {error}")
            send_message = None

        return send_message

    @staticmethod
    async def watch_mailbox_for_updates(db: Session, user_id: UUID, label_ids: list = ["INBOX"]):
        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.modify", 
        ]

        try:
            creds = AuthService.get_google_credentials(db, user_id, provider, scopes)
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None

        try:
            service = build("gmail", "v1", credentials=creds)

            watch_request_body = {
                'topicName': settings.google_cloud_email_topic,
                'labelIds': label_ids,
                # Setting behavior to INCLUDE means a notification is generated 
                # if the email has one of the labels in label_ids (e.g., INBOX).
                'labelFilterBehavior': 'INCLUDE' 
            }

            watch_response = (
                service.users()
                .watch(userId='me', body=watch_request_body)
                .execute()
            )

            print(f"Watch successful for user {user_id}.")
            print(f"Current History ID: {watch_response.get('historyId')}")
            print(f"Expiration: {watch_response.get('expiration')}")
            
            return watch_response

        except HttpError as error:
            print(f"An error occurred during users.watch: {error}")
            return None
