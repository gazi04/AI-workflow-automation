from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.schemas.connection_status_response import (
    SUPPORTED_PROVIDERS,
    ConnectionStatusResponse,
    IntegrationStatus,
)
from auth.scopes import GOOGLE_SCOPES, SLACK_SCOPES
from auth.services.account_service import AccountService
from core.config_loader import settings
from core.database import get_db
from core.setup_logging import setup_logger
from user.models import User

connection_router = APIRouter(prefix="/connection", tags=["Connection"])
logger = setup_logger("Connection Router")

# Scopes each provider's grant must cover. A grant is never widened on refresh,
# so an account connected before a scope was added keeps failing its API calls
# with 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT — an HttpError the credential layer
# never sees. Comparing what was granted against what we now need is the only
# way to surface it.
REQUIRED_SCOPES = {"google": set(GOOGLE_SCOPES), "slack": set(SLACK_SCOPES)}

# Providers whose token has no refresh token by design (Slack bot tokens are
# long-lived). For these, a missing refresh token is normal, not a breakage —
# reconnect is driven by the access token being cleared instead.
PROVIDERS_WITHOUT_REFRESH_TOKEN = {"slack"}


def _is_missing_scopes(provider: str, granted: str | None) -> bool:
    """True when the stored grant is known to be missing a scope we now require.

    A null/empty `scope` column means the grant predates us recording it — we
    can't tell, and nagging every legacy account would be worse than the silent
    403 this is meant to prevent.
    """
    required = REQUIRED_SCOPES.get(provider)
    if not required or not granted:
        return False

    return not required.issubset(set(granted.split()))


@connection_router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Returns the connectivity status of all supported integrations for the current user.
    """
    accounts = await AccountService.get_all_user_accounts(db, user.id)

    account_map = {acc.provider: acc for acc in accounts}

    integrations = []

    for provider in SUPPORTED_PROVIDERS:
        # Hide a provider the deployment hasn't configured rather than render a
        # dead "Connect" button.
        if provider == "slack" and settings.slack_oauth_client_id is None:
            continue

        account = account_map.get(provider)

        if account:
            if provider in PROVIDERS_WITHOUT_REFRESH_TOKEN:
                needs_reconnect = account.access_token is None or _is_missing_scopes(
                    provider, account.scope
                )
            else:
                needs_reconnect = account.refresh_token is None or _is_missing_scopes(
                    provider, account.scope
                )

            email = None
            if account.metadata_account and isinstance(account.metadata_account, dict):
                email = account.metadata_account.get(
                    "email"
                ) or account.metadata_account.get("team_name")

            integrations.append(
                IntegrationStatus(
                    provider=provider,
                    is_connected=True,
                    email=email,
                    needs_reconnect=needs_reconnect,
                )
            )
        else:
            integrations.append(
                IntegrationStatus(
                    provider=provider,
                    is_connected=False,
                    email=None,
                    needs_reconnect=False,
                )
            )

    return ConnectionStatusResponse(integrations=integrations)
