# The models are imported at the top level to resolve SQLAlchemy mapper
# string resolution and circular-import issues before any DB operation.
import core.models  # noqa: F401

from prefect import flow, get_run_logger
from sqlalchemy import select

from core.database import db_session
from core.setup_logging import setup_logger
from auth.models.connected_account import ConnectedAccount
from auth.services.account_service import AccountService
from gmail.services.gmail_service import GmailService


@flow(name="Renew Gmail Watches", log_prints=True)
async def renew_gmail_watches():
    """Re-arm the Gmail `users.watch` for every connected Google account.

    Gmail push subscriptions expire after ~7 days and are otherwise only armed at
    login. This flow runs daily and blindly re-watches every connected account.
    `users.watch` is idempotent — each call resets the 7-day clock and returns a
    fresh historyId — so no expiration bookkeeping is needed.
    """
    # Prefect's run logger surfaces output in the run logs; fall back to the local
    # logger when there is no Prefect run context (e.g. unit tests calling .fn).
    try:
        logger = get_run_logger()
    except Exception:
        logger = setup_logger("Renew Gmail Watches")

    async with db_session() as db:
        result = await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.provider == "google",
                ConnectedAccount.is_connected.is_(True),
            )
        )
        accounts = result.scalars().all()
        # Snapshot the ids before re-watching so the session can close.
        user_ids = [account.user_id for account in accounts]

    logger.info(f"Re-watching {len(user_ids)} connected Google account(s)")

    for user_id in user_ids:
        try:
            resp = await GmailService.watch_mailbox_for_updates(user_id=user_id)
            if resp and resp.get("historyId"):
                async with db_session() as db:
                    account = await AccountService.get_account_by_user_and_provider(
                        db, user_id, "google"
                    )
                    await AccountService.update_history_id(
                        db, account, resp["historyId"]
                    )
                logger.info(f"Re-watched account for user {user_id}")
            else:
                logger.warning(f"Re-watch returned no historyId for user {user_id}")
        except Exception as e:
            # One bad account must not abort the rest of the batch.
            logger.error(f"Re-watch failed for user {user_id}: {e}")
