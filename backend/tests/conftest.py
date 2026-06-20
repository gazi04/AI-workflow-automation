import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.models  # noqa: F401, E402 — registers all ORM models with Base

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.database import engine, get_db
from main import app
from auth.models.connected_account import ConnectedAccount
from auth.models.refresh_token import RefreshToken
from auth.utils import create_access_token, create_refresh_token
from user.models.user import User


# ---------------------------------------------------------------------------
# Async backend (used by anyio-based tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Database — nested transaction rollback for test isolation.
# Each test gets its own transaction that rolls back after the test,
# so no data leaks between tests and the DB stays clean.
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI test client with DB override
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session):
    """HTTP test client with get_db overridden to use the test session."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Common model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user(db_session: Session) -> User:
    """A unique test user per test. Rolled back after the test."""
    user = User(
        email=f"test_{uuid4()}@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()  # assigns id without committing
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Authorization header with a valid JWT for test_user."""
    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(db_session: Session) -> User:
    """A second distinct user, for cross-user/ownership tests."""
    user = User(
        email=f"second_{uuid4()}@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def second_auth_headers(second_user: User) -> dict:
    """Authorization header with a valid JWT for second_user."""
    token = create_access_token(
        {"sub": str(second_user.id), "email": second_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_refresh_token(db_session: Session, test_user: User) -> str:
    """A valid refresh token in the DB for test_user. Returns the token string."""
    token_str, expires_at = create_refresh_token(test_user.id)
    db_session.add(
        RefreshToken(
            user_id=test_user.id,
            token=token_str,
            expires_at=expires_at,
            is_revoked=False,
        )
    )
    db_session.flush()
    return token_str


@pytest.fixture
def expired_refresh_token(db_session: Session, test_user: User) -> str:
    """A refresh token that is already expired."""
    token_str = str(uuid4())
    db_session.add(
        RefreshToken(
            user_id=test_user.id,
            token=token_str,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_revoked=False,
        )
    )
    db_session.flush()
    return token_str


@pytest.fixture
def revoked_refresh_token(db_session: Session, test_user: User) -> str:
    """A refresh token that has been revoked."""
    token_str = str(uuid4())
    db_session.add(
        RefreshToken(
            user_id=test_user.id,
            token=token_str,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            is_revoked=True,
        )
    )
    db_session.flush()
    return token_str


@pytest.fixture
def test_connected_account(db_session: Session, test_user: User) -> ConnectedAccount:
    """A Google connected account for test_user with non-expired tokens."""
    account = ConnectedAccount(
        user_id=test_user.id,
        provider="google",
        provider_account_id=f"google_{uuid4()}",
        is_connected=True,
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scope="https://www.googleapis.com/auth/gmail.readonly",
        metadata_account={"email": test_user.email, "name": "Test User"},
        last_synced_history_id="99999",
    )
    db_session.add(account)
    db_session.flush()
    return account
