from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid import UUID
from sqlalchemy.orm import Session

from auth.services.account_service import AccountService
from auth.services.auth_service import AuthService
from core.config_loader import settings
from core.database import db_session
from core.setup_logging import setup_logger
from user.services.user_service import UserService

logger = setup_logger("Gmail Service")
info_logger = setup_logger("Gmail Service", "info.log")

class GmailService:
    @staticmethod
    async def watch_mailbox_for_updates(
        db: Session, user_id: UUID, label_ids: list = ["INBOX"]
    ) -> dict[str, str] | None:
        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
        ]

        try:
            creds = AuthService.get_google_credentials(db, user_id, provider, scopes)
        except Exception as e:
            logger.error(f"Error retrieving credentials: {e}")
            return 

        try:
            service = build("gmail", "v1", credentials=creds)

            watch_request_body = {
                "topicName": settings.google_cloud_email_topic,
                "labelIds": label_ids,
                # Setting behavior to INCLUDE means a notification is generated
                # if the email has one of the labels in label_ids (e.g., INBOX).
                "labelFilterBehavior": "INCLUDE",
            }

            watch_response = (
                service.users().watch(userId="me", body=watch_request_body).execute()
            )

            info_logger.info(f"Watch successful for user {user_id}.")
            info_logger.info(f"Current History ID: {watch_response.get('historyId')}")
            info_logger.info(f"Expiration: {watch_response.get('expiration')}")

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

            connected_account = await AccountService.get_account(db, user.id, "google")
            last_synced_history_id = connected_account.last_synced_history_id

            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = AuthService.get_google_credentials(db, user.id, "google", scopes)

            try:
                service = build("gmail", "v1", credentials=creds)

                # Using the History API to find out *what* changed
                # Start searching from the LAST successful sync ID (or the one from watch() if first time)
                history_response = (
                    service.users()
                    .history()
                    .list(userId="me", startHistoryId=last_synced_history_id)
                    .execute()
                )

                for history_record in history_response.get("history", []):
                    if "messagesAdded" in history_record:
                        for message_item in history_record["messagesAdded"]:
                            message_id = message_item["message"]["id"]

                            # Fetch the full message content
                            try:
                                full_message = (
                                    service.users()
                                    .messages()
                                    .get(userId="me", id=message_id)
                                    .execute()
                                )
                            except HttpError as e:
                                if e.status_code == 404:
                                    logger.warning(f"Message {message_id} not found (likely deleted). Skipping.")
                                    continue

                                logger.error(f"Unhandled http error occurred: \n{e}")

                            # 🟢 todo: triggering prefect deployment
                            # todo: ✨ implement the feature later on that based workflow will
                            # be decided what should be triggered
                            # note: 📔 the workflow should pass the trigger function to
                            # this handle_fmail_update() function

                await AccountService.update_history_id(
                    db, connected_account, new_history_id
                )

            except HttpError as error:
                logger.error(f"Gmail History API error for {email_address}: {error}")
                return 
            except Exception as e:
                logger.error(f"General processing error for {email_address}: {e}")
                return 
