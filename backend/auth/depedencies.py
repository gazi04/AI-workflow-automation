from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from core.cookies import ACCESS_COOKIE
from core.database import get_db
from user.models.user import User
from user.services.user_service import UserService
from utils.security import decode_access_token

import uuid


# auto_error=False so a missing Authorization header falls back to the cookie.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    token: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Retrieve and validate the current authenticated user. The access token is read
    from the HttpOnly `access_token` cookie, falling back to the Authorization
    header (used by tests and non-browser clients).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    raw_token = request.cookies.get(ACCESS_COOKIE)
    if raw_token is None and token is not None:
        raw_token = token.credentials
    if raw_token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(raw_token)

        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise credentials_exception

    except PyJWTError:
        raise credentials_exception

    user = UserService.get(db, user_id)

    if user is None:
        raise credentials_exception

    return user
