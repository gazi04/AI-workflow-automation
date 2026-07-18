import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.models  # noqa: F401, E402 — registers all ORM models with Base

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import httpx
from asgi_lifespan import LifespanManager
from sqlalchemy.ext.asyncio import AsyncSession

from core.config_loader import settings
from core.cookies import CSRF_COOKIE, generate_csrf_token
from core.database import engine, get_db
from core.rate_limit import limiter
from main import app
from auth.models.connected_account import ConnectedAccount
from auth.models.refresh_token import RefreshToken
from auth.utils import create_access_token, create_refresh_token
from user.models.user import User

# Disable rate limiting suite-wide so endpoints reused across many tests don't
# trip 429s. The dedicated rate-limit test re-enables it within its own scope.
limiter.enabled = False

# Don't hit Prefect from the TestClient lifespan (would block on retries).
settings.register_deployments_on_startup = False

# Local/test env has no Pub/Sub audience; allow the webhook OIDC bypass so the
# payload-parsing tests run without a 503 (the OIDC tests patch settings).
settings.require_pubsub_oidc = False


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
#
# The session is joined to an already-open connection-level transaction via
# join_transaction_mode="create_savepoint", so a `db.commit()` inside
# application code under test only releases a SAVEPOINT — the outer
# transaction (and everything written through it) is discarded by the
# `connection.rollback()` below regardless of how many times the code under
# test calls commit().
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    # asyncpg connections are bound to the event loop that created them, and
    # pytest-asyncio gives each test function its own loop — so any pooled
    # connection from a previous test's loop must be discarded first.
    await engine.dispose()
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )

        yield session

        await session.close()
        await connection.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client with DB override
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_session: AsyncSession):
    """Async HTTP test client with get_db overridden to use the test session.

    Uses httpx.AsyncClient (not the sync TestClient) because the sync
    TestClient runs requests in a background thread with its own event loop —
    incompatible with sharing the fixture's asyncpg-backed AsyncSession, which
    is bound to the event loop that created it.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture
def csrf_headers(client) -> dict:
    """Set the csrf cookie on the client and return the matching header.

    The double-submit CSRF middleware (main.py) rejects mutating requests that
    carry no Authorization header unless X-CSRF-Token matches the csrf cookie.
    """
    token = generate_csrf_token()
    client.cookies.set(CSRF_COOKIE, token)
    return {"X-CSRF-Token": token}


# ---------------------------------------------------------------------------
# Common model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A unique test user per test. Rolled back after the test."""
    user = User(
        email=f"test_{uuid4()}@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()  # assigns id without committing
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Authorization header with a valid JWT for test_user."""
    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def second_user(db_session: AsyncSession) -> User:
    """A second distinct user, for cross-user/ownership tests."""
    user = User(
        email=f"second_{uuid4()}@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def second_auth_headers(second_user: User) -> dict:
    """Authorization header with a valid JWT for second_user."""
    token = create_access_token(
        {"sub": str(second_user.id), "email": second_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_refresh_token(db_session: AsyncSession, test_user: User) -> str:
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
    await db_session.flush()
    return token_str


@pytest.fixture
async def expired_refresh_token(db_session: AsyncSession, test_user: User) -> str:
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
    await db_session.flush()
    return token_str


@pytest.fixture
async def revoked_refresh_token(db_session: AsyncSession, test_user: User) -> str:
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
    await db_session.flush()
    return token_str


@pytest.fixture
async def test_connected_account(
    db_session: AsyncSession, test_user: User
) -> ConnectedAccount:
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
    await db_session.flush()
    return account
