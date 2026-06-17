from datetime import datetime, timedelta, timezone
from jwt import PyJWTError
from passlib.context import CryptContext
from typing import Optional

from core.config_loader import settings

import hashlib
import uuid
import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_secret_key():
    key = settings.jwt_secret_key
    if key is None:
        raise ValueError("JWT_SECRET_KEY environment variable is not set!")
    return key


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    refresh_token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return refresh_token, expires_at


def hash_refresh_token(raw: str) -> str:
    """Hash a refresh token for storage so a DB leak can't yield valid sessions.

    SHA-256 is sufficient for high-entropy tokens (UUID4); no salt needed since
    the input is not low-entropy like a password. The 64-char hex digest fits the
    existing String(255) column.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[settings.algorithm],
            # Options like verify_signature/verify_aud are handled differently
            # or implicitly in PyJWT compared to python-jose.
        )
        return payload
    except PyJWTError as e:
        # 🔴 todo: catch specific PyJWT exceptions (ExpiredSignatureError, InvalidSignatureError, etc.)
        # and re-raise them as the standard PyJWTError
        raise PyJWTError(f"Token validation failed: {e}")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
