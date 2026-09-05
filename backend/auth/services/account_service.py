from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.connected_account import ConnectedAccount
from core.crypto import encrypt_token


class AccountService:
    @staticmethod
    async def get_account_by_user_and_provider(
        db: AsyncSession, user_id: UUID, provider: str
    ) -> Optional[ConnectedAccount]:
        result = await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_user_accounts(
        db: AsyncSession, user_id: UUID
    ) -> List[ConnectedAccount]:
        result = await db.execute(
            select(ConnectedAccount).where(ConnectedAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession,
        token: str,
        expiry,
        account: ConnectedAccount | None = None,
        user_id: UUID | None = None,
        provider: str | None = None,
        refresh_token: Any | None = None,
    ) -> ConnectedAccount:
        """
        Refreshes the tokens of a account, first reason to implement was the mainly for
        google api calls to validate the credentials.

        For the parameters you can pass directly down the model and refresh the tokens
        or else you can pass the user id with the provider
        Refresh token should also be updated if it changed, even though this happens more rarely
        """
        if account is None and user_id is not None and provider is not None:
            account = await AccountService.get_account_by_user_and_provider(
                db, user_id, provider
            )

        if account is None:
            raise ValueError(
                f"No connected account to refresh (user_id={user_id}, provider={provider})"
            )

        account.access_token = encrypt_token(token)
        account.token_expires_at = expiry

        if refresh_token is not None:
            account.refresh_token = encrypt_token(refresh_token)

        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def upsert_from_oauth(
        db: AsyncSession,
        user_id: UUID,
        provider: str,
        provider_account_id: str,
        access_token: str,
        refresh_token: str | None,
        token_expires_at: datetime | None,
        scope: str | None,
        metadata_account: dict | None = None,
        mark_connected: bool = False,
        update_metadata_on_existing: bool = False,
    ) -> ConnectedAccount:
        """Create or update a ConnectedAccount after a fresh OAuth callback.

        Tokens are encrypted here via core.crypto.encrypt_token, matching
        refresh_tokens()'s convention. A falsy refresh_token on update leaves
        the existing encrypted refresh_token untouched (providers may omit it
        on repeat consent).
        """
        account = await AccountService.get_account_by_user_and_provider(
            db, user_id, provider
        )

        if account is None:
            account = ConnectedAccount(
                user_id=user_id,
                provider=provider,
                provider_account_id=provider_account_id,
                metadata_account=metadata_account or {},
            )
            db.add(account)
        elif update_metadata_on_existing:
            account.provider_account_id = (
                provider_account_id or account.provider_account_id
            )
            if metadata_account is not None:
                account.metadata_account = metadata_account

        account.access_token = encrypt_token(access_token)
        if refresh_token:
            account.refresh_token = encrypt_token(refresh_token)
        account.token_expires_at = token_expires_at
        account.scope = scope
        account.updated_at = datetime.now(timezone.utc)

        if mark_connected:
            account.is_connected = True

        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def update_history_id(
        db: AsyncSession, account: ConnectedAccount, new_history_id: str
    ) -> ConnectedAccount:
        account.last_synced_history_id = new_history_id
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def set_sync_pending(
        db: AsyncSession, account: ConnectedAccount, value: bool
    ) -> ConnectedAccount:
        account.sync_pending = value
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def bump_observed_history_id(
        db: AsyncSession, account: ConnectedAccount, history_id: str
    ) -> ConnectedAccount:
        """Advance the high-water mark to the newest observed historyId.

        Gmail historyIds are monotonically increasing integers (sent as strings),
        so the newest notification is the numeric max.
        """
        current = account.latest_observed_history_id
        if current is None or int(history_id) > int(current):
            account.latest_observed_history_id = history_id
            await db.commit()
            await db.refresh(account)
        return account
