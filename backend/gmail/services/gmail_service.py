from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from auth.models.connected_account import ConnectedAccount
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
    async def watch_mailbox_for_updates(
        user_id: UUID, label_ids: list = ["INBOX"]
    ) -> dict[str, str] | None:
        provider = "google"
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
        ]

        try:
            async with db_session() as db:
                creds = await AuthService.get_google_credentials(
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
    async def _acquire_account_locked(
        db: AsyncSession, user_id: UUID
    ) -> ConnectedAccount | None:
        """Load the google account row under a FOR UPDATE lock.

        Tries NOWAIT first; on contention retries once with a blocking lock. The
        row lock is only ever held for short bookkeeping commits (never the long
        Gmail fetch), so the blocking wait returns quickly and cannot deadlock
        with a sync that is in progress.
        """
        stmt = select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.provider == "google",
        )
        try:
            result = await db.execute(stmt.with_for_update(nowait=True))
            return result.scalar_one_or_none()
        except OperationalError:
            await db.rollback()
            result = await db.execute(stmt.with_for_update())
            return result.scalar_one_or_none()

    @staticmethod
    async def _release_lock(user_id: UUID):
        """Clear the in-progress timestamp after a failed fetch.

        Leaves ``sync_pending`` untouched so a deferred notification is retried
        by the next notification (or the staleness takeover).
        """
        async with db_session() as db:
            acc = await AccountService.get_account_by_user_and_provider(
                db, user_id, "google"
            )
            if acc:
                acc.last_synced_started_at = None
                await db.commit()

    @staticmethod
    async def _reset_baseline(user_id: UUID, target: str) -> None:
        """Adopt ``target`` as the new baseline and release the lock.

        Used when the stored startHistoryId is missing or too old (Gmail returns
        404): that history window is gone, so resync forward from the latest
        observed id instead of retrying a dead id forever.
        """
        async with db_session() as db:
            account = await GmailService._acquire_account_locked(db, user_id)
            if account:
                account.last_synced_history_id = target
                account.last_synced_started_at = None
                account.sync_pending = False
                await db.commit()

    @staticmethod
    async def handle_gmail_update(email_address: str, new_history_id: str):
        """
        Runs in the background. Fetches changes since the last sync and triggers actions.
        """
        # --- Phase 1: claim ownership or defer -----------------------------
        async with db_session() as db:
            user = await UserService.get_by_email(db, email_address)

            if not user:
                logger.error(f"User not found for email: {email_address}")
                return

            user_id = user.id  # to use outside the with statment

            account = await GmailService._acquire_account_locked(db, user_id)
            if not account:
                logger.error(f"No google account connected for {email_address}")
                return

            # Record this notification as the newest observed historyId. Done
            # in-memory; the single commit below persists it while still holding
            # the row lock, keeping the defer/claim decision atomic.
            if account.latest_observed_history_id is None or int(new_history_id) > int(
                account.latest_observed_history_id
            ):
                account.latest_observed_history_id = new_history_id

            now = datetime.now(timezone.utc)
            sync_in_progress = (
                account.last_synced_started_at is not None
                and now - account.last_synced_started_at < timedelta(minutes=1)
            )

            if sync_in_progress:
                # Defer instead of dropping: flag pending so the owning sync
                # re-runs one more cumulative fetch after it finishes.
                account.sync_pending = True
                await db.commit()
                logger.info(f"Deferring sync for {email_address} - flagged pending.")
                return

            # Become the owner. The commit releases the row lock; the timestamp
            # keeps guarding the long fetch (1-minute staleness takeover).
            account.last_synced_started_at = now
            account.sync_pending = False
            await db.commit()

            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = await AuthService.get_google_credentials(
                db, user_id, "google", scopes
            )

        # --- Phase 2: drain loop -------------------------------------------
        # Each pass fetches cumulatively from the baseline. A notification that
        # arrives mid-fetch bumps the high-water mark and sets sync_pending,
        # which forces one more pass — so nothing is dropped.
        while True:
            async with db_session() as db:
                account = await AccountService.get_account_by_user_and_provider(
                    db, user_id, "google"
                )
                baseline = account.last_synced_history_id
                # Snapshot the high-water mark BEFORE fetching.
                target = account.latest_observed_history_id or new_history_id

            if baseline is None:
                # Never completed a watch (or a prior stale-history reset): adopt
                # the latest observed id and wait for the next notification rather
                # than calling history.list with None.
                await GmailService._reset_baseline(user_id, target)
                return

            try:
                async with GmailHistoryProcessor(creds, user_id) as processor:
                    await processor.fetch_and_process(baseline)
            except HttpError as error:
                if getattr(error.resp, "status", None) == 404:
                    # startHistoryId older than Gmail's ~1 week window — resync
                    # forward from the latest id instead of failing on it forever.
                    logger.warning(
                        f"Stale startHistoryId for {email_address}; "
                        f"resetting baseline to {target}."
                    )
                    await GmailService._reset_baseline(user_id, target)
                    return
                logger.error(f"Gmail History API error for {email_address}: {error}")
                await GmailService._release_lock(user_id)
                return
            except Exception as e:
                logger.error(f"General processing error for {email_address}: {e}")
                await GmailService._release_lock(user_id)
                return

            # Bookkeeping under the row lock, committed atomically: advance the
            # baseline and decide whether another pass is needed.
            async with db_session() as db:
                account = await GmailService._acquire_account_locked(db, user_id)
                account.last_synced_history_id = target

                if account.sync_pending:
                    # More notifications landed during the fetch — drain again.
                    account.sync_pending = False
                    account.last_synced_started_at = datetime.now(timezone.utc)
                    await db.commit()
                    continue

                # Nothing pending — release the logical lock and finish.
                account.last_synced_started_at = None
                await db.commit()
                break

    @staticmethod
    async def get_latest_message_id(user_id: UUID):
        """
        The method is for testing purpose
        """
        async with db_session() as db:
            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = await AuthService.get_google_credentials(
                db, user_id, "google", scopes
            )

        with build("gmail", "v1", credentials=creds) as service:
            results = (
                service.users().messages().list(userId="me", maxResults=1).execute()
            )
            messages = results.get("messages", [])
            if not messages:
                return None
            return messages[0]["id"]

    @staticmethod
    async def get_latest_message(user_id: UUID):
        """
        The method is for testing purpose
        """
        async with db_session() as db:
            scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = await AuthService.get_google_credentials(
                db, user_id, "google", scopes
            )

        with build("gmail", "v1", credentials=creds) as service:
            results = (
                service.users().messages().list(userId="me", maxResults=1).execute()
            )
            messages = results.get("messages", [])
            if not messages:
                return None
            return messages
