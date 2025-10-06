from fastapi import HTTPException
from sqlalchemy.orm import Session
import uuid

from auth.models.refresh_token import RefreshToken
from auth.utils import create_access_token, create_refresh_token, get_password_hash, verify_password
from user.models.user import User
from auth.schemas.user_login import UserLogin
from user.services.user_service import UserService


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
    def get_google_flow():
        # OAuth configuration
        pass

    @staticmethod
    def validate_google_token(credentials):
        # Google token verification
        pass

    @staticmethod
    def handle_connected_account(db: Session, user: User, user_info: dict, credentials):
        # Connected account upsert logic
        pass
