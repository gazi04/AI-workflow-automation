from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from auth.services.oauth_service import OAuthStateService
from auth.models.oauth_state import OAuthState


def make_mock_db(record=None):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=mock_result)
    # db.add(...) is called synchronously (never awaited) by the code under
    # test; keep it a plain MagicMock to avoid "coroutine was never awaited".
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# OAuthStateService.create
# ---------------------------------------------------------------------------

async def test_create_adds_record_and_commits():
    db = make_mock_db()
    await OAuthStateService.create(db, "test-state-123")
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_create_returns_oauth_state_instance():
    db = make_mock_db()
    result = await OAuthStateService.create(db, "test-state-456")
    assert isinstance(result, OAuthState)


async def test_create_sets_state_value():
    db = make_mock_db()
    result = await OAuthStateService.create(db, "my-state")
    assert result.state == "my-state"


async def test_create_sets_expiry_approximately_10_minutes_ahead():
    db = make_mock_db()
    before = datetime.now(timezone.utc)
    result = await OAuthStateService.create(db, "state-ttl")
    after = datetime.now(timezone.utc)

    assert result.expires_at >= before + timedelta(minutes=9, seconds=59)
    assert result.expires_at <= after + timedelta(minutes=10, seconds=1)


# ---------------------------------------------------------------------------
# OAuthStateService.consume
# ---------------------------------------------------------------------------

async def test_consume_valid_state_returns_true():
    record = MagicMock()
    record.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    db = make_mock_db(record)

    result = await OAuthStateService.consume(db, "valid-state")

    assert result is True
    db.delete.assert_called_once_with(record)
    db.commit.assert_called_once()


async def test_consume_missing_state_returns_false():
    db = make_mock_db(record=None)

    result = await OAuthStateService.consume(db, "unknown-state")

    assert result is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()


async def test_consume_expired_state_returns_false():
    record = MagicMock()
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db = make_mock_db(record)

    result = await OAuthStateService.consume(db, "expired-state")

    assert result is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()
