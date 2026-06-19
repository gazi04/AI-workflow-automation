from datetime import datetime, timezone, timedelta
from uuid import uuid4

from auth.models.oath_state import OAuthState
from auth.services.oauth_service import OAuthStateService


def _make_state() -> str:
    return f"state-{uuid4()}"


# ---------------------------------------------------------------------------
# OAuthStateService.create — real DB round-trips
# ---------------------------------------------------------------------------

def test_create_persists_row(db_session):
    state = _make_state()
    OAuthStateService.create(db_session, state)

    row = db_session.query(OAuthState).filter_by(state=state).first()
    assert row is not None
    assert row.state == state


def test_create_row_has_future_expiry(db_session):
    state = _make_state()
    OAuthStateService.create(db_session, state)

    row = db_session.query(OAuthState).filter_by(state=state).first()
    assert row.expires_at > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# OAuthStateService.consume — real DB round-trips
# ---------------------------------------------------------------------------

def test_consume_valid_returns_true_and_deletes_row(db_session):
    state = _make_state()
    OAuthStateService.create(db_session, state)

    result = OAuthStateService.consume(db_session, state)

    assert result is True
    row = db_session.query(OAuthState).filter_by(state=state).first()
    assert row is None


def test_consume_expired_returns_false_and_leaves_row(db_session):
    state = _make_state()
    record = OAuthState(
        state=state,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(record)
    db_session.flush()

    result = OAuthStateService.consume(db_session, state)

    assert result is False
    row = db_session.query(OAuthState).filter_by(state=state).first()
    assert row is not None


def test_consume_nonexistent_returns_false(db_session):
    result = OAuthStateService.consume(db_session, "state-does-not-exist")
    assert result is False


def test_consume_is_idempotent(db_session):
    state = _make_state()
    OAuthStateService.create(db_session, state)

    first = OAuthStateService.consume(db_session, state)
    second = OAuthStateService.consume(db_session, state)

    assert first is True
    assert second is False
