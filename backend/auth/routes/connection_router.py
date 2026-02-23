from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.depedencies import get_current_user
from auth.schemas.connection_status_response import (
    SUPPORTED_PROVIDERS,
    ConnectionStatusResponse,
    IntegrationStatus,
)
from auth.services.account_service import AccountService
from core.database import get_db
from core.setup_logging import setup_logger
from user.models import User

connection_router = APIRouter(prefix="/connection", tags=["Connection"])
logger = setup_logger("Connection Router")


@connection_router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Returns the connectivity status of all supported integrations for the current user.
    """
    accounts = AccountService.get_all_user_accounts(db, user.id)

    account_map = {acc.provider: acc for acc in accounts}

    integrations = []

    for provider in SUPPORTED_PROVIDERS:
        account = account_map.get(provider)

        if account:
            needs_reconnect = account.refresh_token is None

            email = None
            if account.metadata_account and isinstance(account.metadata_account, dict):
                email = account.metadata_account.get("email")

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
