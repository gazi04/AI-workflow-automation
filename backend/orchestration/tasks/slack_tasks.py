import asyncio
from typing import Any, Dict
from uuid import UUID

import httpx
from prefect import task

from auth.services.auth_service import AuthService
from core.database import db_session
from core.setup_logging import setup_logger

logger = setup_logger("Prefect Slack Task")

PROVIDER = "slack"

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

# Slack error codes that mean the grant itself is dead — the account gets
# flagged for reconnect and the failure is reported with this hint.
_AUTH_ERRORS = {"invalid_auth", "token_revoked", "account_inactive", "not_authed"}
# Slack error codes that mean the workflow config is wrong, not the connection.
_CHANNEL_ERRORS = {"channel_not_found", "not_in_channel", "is_archived"}

SLACK_RECONNECT_HINT = (
    "Slack revoked access for this workspace. Reconnect it from the Integrations "
    "page, then run this workflow again."
)


def _fetch_bot_token(user_id: UUID) -> str:
    async def _fetch() -> str:
        async with db_session() as db:
            return await AuthService.get_slack_bot_token(db, user_id)

    return asyncio.run(_fetch())


def _mark_disconnected(user_id: UUID) -> None:
    async def _mark() -> None:
        async with db_session() as db:
            await AuthService.mark_account_disconnected(db, user_id, PROVIDER)

    asyncio.run(_mark())


@task(name="Send Slack message", retries=2, retry_delay_seconds=30, log_prints=True)
def send_slack_message(user_id: UUID, channel: str, message: str) -> Dict[str, Any]:
    """
    Post `message` to `channel` as the connected Slack bot.

    `channel` may be a name (`#general`) or an ID (`C0123…`). The bot must be a
    member of private channels. Returns the resolved channel ID and the message
    timestamp so a downstream node can reference `{{node_id.ts}}`.
    """
    token = _fetch_bot_token(user_id)

    try:
        response = httpx.post(
            SLACK_POST_MESSAGE_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": message},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # Network / 5xx — let Prefect retry.
        logger.error(f"Slack request failed: {error}")
        raise

    data = response.json()

    if not data.get("ok"):
        err = data.get("error", "unknown")

        if err in _AUTH_ERRORS:
            logger.error(f"Slack auth rejected for user {user_id}: {err}")
            _mark_disconnected(user_id)
            raise PermissionError(SLACK_RECONNECT_HINT)

        if err in _CHANNEL_ERRORS:
            raise ValueError(
                f"Slack channel problem ({err}). Check the channel name and that "
                "the bot has been invited to it."
            )

        raise RuntimeError(f"Slack API error: {err}")

    logger.info(f"Posted Slack message to {data['channel']} (ts {data['ts']})")

    return {"status": "sent", "channel": data["channel"], "ts": data["ts"]}
