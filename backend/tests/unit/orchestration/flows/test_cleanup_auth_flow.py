from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from orchestration.flows.cleanup_auth_flow import cleanup_expired_auth


@asynccontextmanager
async def fake_db_session(session):
    yield session


async def test_purges_all_three_auth_tables():
    session = AsyncMock()
    # Each model's filtered delete returns a rowcount.
    mock_result = MagicMock(rowcount=3)
    session.execute = AsyncMock(return_value=mock_result)

    with patch(
        "orchestration.flows.cleanup_auth_flow.db_session",
        side_effect=lambda: fake_db_session(session),
    ):
        await cleanup_expired_auth.fn()

    # One filtered delete + commit per table (OAuthState, AuthCode, RefreshToken).
    assert session.execute.call_count == 3
    assert session.commit.call_count == 3
    session.rollback.assert_not_called()


async def test_one_table_failure_does_not_abort_the_rest():
    session = AsyncMock()
    # First table's delete raises; the remaining two must still run.
    session.execute = AsyncMock(
        side_effect=[
            RuntimeError("boom"),
            MagicMock(rowcount=5),
            MagicMock(rowcount=7),
        ]
    )

    with patch(
        "orchestration.flows.cleanup_auth_flow.db_session",
        side_effect=lambda: fake_db_session(session),
    ):
        await cleanup_expired_auth.fn()

    # All three tables attempted; the failing one rolled back, the others committed.
    assert session.execute.call_count == 3
    session.rollback.assert_called_once()
    assert session.commit.call_count == 2
