from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid import UUID

from auth.services.account_service import AccountService
from auth.services.auth_service import AuthService
from core.config_loader import settings
from core.database import db_session
from core.processors.gmail_history_processor import GmailHistoryProcessor
from core.setup_logging import setup_logger
from user.services.user_service import UserService

logger = setup_logger("Gmail Service")


class GmailService:
    @staticmethod
    async def watch_mailbox_for_updates(
        user_id: UUID, label_ids: list = ["INBOX"]
    ) -> dict[str, str] | None:
        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
        ]

        try:
            with db_session() as db:
                creds = AuthService.get_google_credentials(
                    db, user_id, provider, scopes
                )
        except Exception as e:
            logger.error(f"Error retrieving credentials: {e}")
            return

        try:
            watch_request_body = {
                "topicName": settings.google_cloud_email_topic,
                "labelIds": label_ids,
                # Setting behavior to INCLUDE means a notification is generated
                # if the email has one of the labels in label_ids (e.g., INBOX).
                "labelFilterBehavior": "INCLUDE",
            }

            with build("gmail", "v1", credentials=creds) as service:
                watch_response = (
                    service.users()
                    .watch(userId="me", body=watch_request_body)
                    .execute()
                )

            return watch_response

        except HttpError as error:
            logger.error(f"An error occurred during users.watch: {error}")
            return

    @staticmethod
    async def handle_gmail_update(email_address: str, new_history_id: str):
        """
        Runs in the background. Fetches changes since the last sync and triggers actions.
        """
        with db_session() as db:
            user = await UserService.get_by_email(db, email_address)

            if not user:
                logger.error(f"User not found for email: {email_address}")
                return

            user_id = user.id # to use outside the with statment

            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            connected_account = await AccountService.get_account(db, user.id, "google")
            creds = AuthService.get_google_credentials(db, user.id, "google", scopes)

            last_synced_history_id = connected_account.last_synced_history_id

        try:
            with GmailHistoryProcessor(creds, user_id) as processor:
                await processor.fetch_and_process(last_synced_history_id)

            with db_session() as db:
                connected_account = await AccountService.get_account(
                    db, user_id, "google"
                )
                await AccountService.update_history_id(
                    db, connected_account, new_history_id
                )

        except HttpError as error:
            logger.error(f"Gmail History API error for {email_address}: {error}")
            return
        except Exception as e:
            logger.error(f"General processing error for {email_address}: {e}")
            return
