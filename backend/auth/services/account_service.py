from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from auth.models.connected_account import ConnectedAccount


class AccountService:
    @staticmethod
    def get_account_by_user_and_provider(
        db: Session, user_id: UUID, provider: str
    ) -> ConnectedAccount:
        return (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider,
            )
            .first()
        )

    @staticmethod
    def refresh_tokens(
        db: Session,
        token: str,
        expiry,
        account: ConnectedAccount | None = None,
        user_id: UUID | None = None,
        provider: str | None = None,
        refresh_token: None | Any = None,
    ) -> ConnectedAccount:
        """
        Refreshes the tokens of a account, first reason to implement was the mainly for
        google api calls to validate the credentials.

        For the parameters you can pass directly down the model and refresh the tokens
        or else you can pass the user id with the provider
        Refresh token should also be updated if it changed, even though this happens more rarely
        """
        if account is None and user_id is not None and provider is not None:
            account = AccountService.get_account_by_id_and_provider(
                db, user_id, provider
            )

        account.access_token = token
        account.token_expires_at = expiry

        if refresh_token is not None:
            account.refresh_token = refresh_token

        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def update_history_id(
        db: Session, account: ConnectedAccount, new_history_id: str
    ) -> ConnectedAccount:
        account.last_synced_history_id = new_history_id
        db.commit()
        db.refresh(account)
        return account
