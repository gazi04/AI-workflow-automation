from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select

from auth.models.oauth_state import OAuthState
from auth.services.oauth_service import OAuthStateService


def _make_state() -> str:
    return f"state-{uuid4()}"


# ---------------------------------------------------------------------------
# OAuthStateService.create — real DB round-trips
# ---------------------------------------------------------------------------

async def test_create_persists_row(db_session):
    state = _make_state()
    await OAuthStateService.create(db_session, state)

    result = await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.state == state


async def test_create_row_has_future_expiry(db_session):
    state = _make_state()
    await OAuthStateService.create(db_session, state)

    result = await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    row = result.scalar_one_or_none()
    assert row.expires_at > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# OAuthStateService.consume — real DB round-trips
# ---------------------------------------------------------------------------

async def test_consume_valid_returns_true_and_deletes_row(db_session):
    state = _make_state()
    await OAuthStateService.create(db_session, state)

    result = await OAuthStateService.consume(db_session, state)

    assert result is True
    query_result = await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    row = query_result.scalar_one_or_none()
    assert row is None


async def test_consume_expired_returns_false_and_leaves_row(db_session):
    state = _make_state()
    record = OAuthState(
        state=state,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(record)
    await db_session.flush()

    result = await OAuthStateService.consume(db_session, state)

    assert result is False
    query_result = await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    row = query_result.scalar_one_or_none()
    assert row is not None


async def test_consume_nonexistent_returns_false(db_session):
    result = await OAuthStateService.consume(db_session, "state-does-not-exist")
    assert result is False


async def test_consume_is_idempotent(db_session):
    state = _make_state()
    await OAuthStateService.create(db_session, state)

    first = await OAuthStateService.consume(db_session, state)
    second = await OAuthStateService.consume(db_session, state)

    assert first is True
    assert second is False
