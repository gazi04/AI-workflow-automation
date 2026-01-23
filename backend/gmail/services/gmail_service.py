from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid import UUID

from auth.services.account_service import AccountService
from auth.services.auth_service import AuthService
from core.config_loader import settings
from core.database import db_session
from core.processors import GmailHistoryProcessor
from core.setup_logging import setup_logger
from user.services.user_service import UserService

logger = setup_logger("Gmail Service")


class GmailService:
    @staticmethod
    def watch_mailbox_for_updates(
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
    def handle_gmail_update(email_address: str, new_history_id: str):
        """
            Runs in the background. Fetches changes since the last sync and triggers actions.
        """
        with db_session() as db:
            user = UserService.get_by_email(db, email_address)

            if not user:
                logger.error(f"User not found for email: {email_address}")
                return

            user_id = user.id  # to use outside the with statment
            connected_account = AccountService.get_account(db, user_id, "google")

            now = datetime.now(timezone.utc)
            if connected_account.last_synced_started_at:
                '''
                 🐛 todo: use queue to push new_history_id
                 In case where notification A arrives on 20:01 and another notification B is send on 20:02
                 the B notification is skipped and also the other notification that will arrive on the 20:01-20:06 time window,
                 so in the worse case scenario that means there is the notification B (not handled) and there isn't any new notification
                 for the upcoming 4 hours. After 4 hours there is a new notification Z but there is still notification B that 
                 was send on 20:02 and wasn't supposed to be handled after 4 hours
                '''
                if now - connected_account.last_synced_started_at < timedelta(
                    minutes=5
                ):
                    logger.info(
                        f"Skipping sync for {email_address} - Sync already in progress."
                    )
                    return

            # Set the lock
            connected_account.last_synced_started_at = now
            db.commit()

            last_synced_history_id = connected_account.last_synced_history_id

            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = AuthService.get_google_credentials(db, user_id, "google", scopes)

        try:
            with GmailHistoryProcessor(creds, user_id) as processor:
                processor.fetch_and_process(last_synced_history_id)

            with db_session() as db:
                connected_account = AccountService.get_account(
                    db, user_id, "google"
                )  # need to query the connected account again cause a SQLAlchemy model doesn't work outside the session
                AccountService.update_history_id(
                    db, connected_account, new_history_id
                )

        except HttpError as error:
            logger.error(f"Gmail History API error for {email_address}: {error}")
            with db_session() as db:
                acc = AccountService.get_account(db, user_id, "google")
                acc.last_synced_started_at = None
                db.commit()
            return
        except Exception as e:
            logger.error(f"General processing error for {email_address}: {e}")
            with db_session() as db:
                acc = AccountService.get_account(db, user_id, "google")
                acc.last_synced_started_at = None
                db.commit()
            return

    @staticmethod
    def get_latest_message_id(user_id: UUID):
        """
            The method is for testing purpose
        """
        with db_session() as db:
            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = AuthService.get_google_credentials(db, user_id, "google", scopes)

        with build("gmail", "v1", credentials=creds) as service:
            results = service.users().messages().list(userId='me', maxResults=1).execute()
            messages = results.get('messages', [])
            if not messages:
                return None
            return messages[0]['id']

