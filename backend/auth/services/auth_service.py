from fastapi import HTTPException
from sqlalchemy.orm import Session
import uuid

from auth.models.refresh_token import RefreshToken
from auth.services.account_service import AccountService
from auth.schemas.user_login import UserLogin
from auth.utils import create_access_token, create_refresh_token, get_password_hash, verify_password
from core.config_loader import settings
from user.models.user import User
from user.services.user_service import UserService
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class AuthService:

    # 🔴 todo: need to handle exceptions
    @staticmethod
    def register_user(db: Session, user_data: UserLogin) -> User:
        hashed_password = get_password_hash(user_data.password)

        return UserService.create_user(
            db,
            user_data.email,
            hashed_password
        )


    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        # Email/password verification logic
        pass

    @staticmethod
    def create_token_pair(db: Session, user: User) -> dict:

        access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
        refresh_token_string, expires_at = create_refresh_token(user.id)

        new_refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_string,
            expires_at=expires_at
        )
        db.add(new_refresh_token)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_string
        }

    @staticmethod
    def refresh_tokens(db: Session, refresh_token: str) -> dict:
        # Token refresh with rotation logic
        pass

    @staticmethod
    def handle_google_oauth(db: Session, code: str, state: str) -> dict:
        # Complete Google OAuth flow logic
        pass

    @staticmethod
    def get_google_flow(db: Session, user_id: uuid.UUID, provider: str, scopes: list) -> Credentials:
        connected_account = AccountService.get_account_by_id_and_provider(db, user_id, provider) # 🔴 todo: make a provider emun for cleaner code
        creds = Credentials(
            token=connected_account.access_token,
            refresh_token=connected_account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            scopes=scopes,
            # scopes=["https://www.googleapis.com/auth/gmail.compose"], # MUST include the correct scope
            # The expiry check is automatically handled by the library
            # but we provide the expiry time from the DB
            # The library expects a 'datetime' object for `token_expiry`
            expiry=connected_account.token_expires_at, 
        )

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                AccountService.refresh_tokens(
                    db,
                    account=connected_account,
                    token=creds.token,
                    refresh_token=creds.refresh_token,
                    expiry=creds.expiry
                )
            except Exception as e:
                raise HTTPException(status_code=401, detail=f"Google token refresh failed {e}")


        return creds

    @staticmethod
    def validate_google_token(credentials):
        # Google token verification
        pass

    @staticmethod
    def handle_connected_account(db: Session, user: User, user_info: dict, credentials):
        # Connected account upsert logic
        pass
