from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import uuid

import jwt
from jwt import PyJWTError

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_secret_key():
    key = os.getenv("JWT_SECRET_KEY")
    if key is None:
        raise ValueError("JWT_SECRET_KEY environment variable is not set!")
    return key


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    refresh_token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return refresh_token, expires_at


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[ALGORITHM],
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
