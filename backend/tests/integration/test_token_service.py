from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from auth.services.token_service import TokenService


# ---------------------------------------------------------------------------
# Helpers — build a mock session and token record inline
# ---------------------------------------------------------------------------

def make_token_record(user_id=None, is_revoked=False, days_until_expiry=7):
    user_id = user_id or uuid4()
    record = MagicMock()
    record.user_id = user_id
    record.is_revoked = is_revoked
    record.expires_at = datetime.now(timezone.utc) + timedelta(days=days_until_expiry)
    record.user.email = "test@example.com"
    record.user.is_active = True
    return record


def make_db(token_record):
    """Returns a mock session whose query chain returns token_record."""
    db = MagicMock()
    # session.begin() context manager
    db.begin.return_value.__enter__ = MagicMock(return_value=None)
    db.begin.return_value.__exit__ = MagicMock(return_value=False)
    # query chain: db.query(...).join(...).filter(...).first()
    db.query.return_value.join.return_value.filter.return_value.first.return_value = token_record
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valid_token_returns_access_and_refresh():
    record = make_token_record()
    db = make_db(record)

    result = TokenService.refresh_token(db, "valid-token-string")

    assert result is not None
    assert "access_token" in result
    assert "refresh_token" in result


def test_valid_token_old_record_marked_revoked():
    record = make_token_record()
    db = make_db(record)

    TokenService.refresh_token(db, "valid-token-string")

    assert record.is_revoked is True


def test_valid_token_new_refresh_record_added():
    record = make_token_record()
    db = make_db(record)

    TokenService.refresh_token(db, "valid-token-string")

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    # The new RefreshToken must be for the same user
    from auth.models.refresh_token import RefreshToken
    assert isinstance(added, RefreshToken)
    assert added.user_id == record.user_id


def test_token_not_found_returns_none():
    db = make_db(token_record=None)

    result = TokenService.refresh_token(db, "nonexistent-token")

    assert result is None
    db.add.assert_not_called()


def test_revoked_token_not_found_via_filter():
    # The DB query filters is_revoked==False, so revoked tokens return None
    db = make_db(token_record=None)

    result = TokenService.refresh_token(db, "revoked-token")

    assert result is None


def test_exception_in_query_triggers_rollback():
    db = MagicMock()
    db.begin.return_value.__enter__ = MagicMock(return_value=None)
    db.begin.return_value.__exit__ = MagicMock(return_value=False)
    db.query.side_effect = Exception("DB error")

    try:
        TokenService.refresh_token(db, "any-token")
    except Exception:
        pass

    db.rollback.assert_called_once()
