from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from orchestration.flows.renew_watches_flow import renew_gmail_watches


def make_account(user_id):
    account = MagicMock()
    account.user_id = user_id
    return account


@asynccontextmanager
async def fake_db_session(session):
    yield session


async def test_rewatches_every_connected_account_and_advances_history_id():
    user_a, user_b = uuid4(), uuid4()

    # Query session returns two connected google accounts.
    query_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        make_account(user_a),
        make_account(user_b),
    ]
    query_session.execute = AsyncMock(return_value=mock_result)
    update_session = AsyncMock()

    with (
        patch(
            "orchestration.flows.renew_watches_flow.db_session",
            side_effect=[
                fake_db_session(query_session),
                fake_db_session(update_session),
                fake_db_session(update_session),
            ],
        ),
        patch(
            "orchestration.flows.renew_watches_flow.GmailService"
        ) as mock_gmail,
        patch(
            "orchestration.flows.renew_watches_flow.AccountService"
        ) as mock_account_service,
    ):
        mock_gmail.watch_mailbox_for_updates = AsyncMock(
            return_value={"historyId": "999"}
        )
        mock_account_service.get_account_by_user_and_provider = AsyncMock(
            return_value=MagicMock()
        )
        mock_account_service.update_history_id = AsyncMock()

        await renew_gmail_watches.fn()

    # Re-watched once per account.
    assert mock_gmail.watch_mailbox_for_updates.call_count == 2
    mock_gmail.watch_mailbox_for_updates.assert_any_call(user_id=user_a)
    mock_gmail.watch_mailbox_for_updates.assert_any_call(user_id=user_b)

    # History id advanced once per account.
    assert mock_account_service.update_history_id.call_count == 2
    for call in mock_account_service.update_history_id.call_args_list:
        assert call.args[2] == "999"


async def test_one_failing_account_does_not_abort_the_rest():
    user_a, user_b = uuid4(), uuid4()

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        make_account(user_a),
        make_account(user_b),
    ]
    session.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "orchestration.flows.renew_watches_flow.db_session",
            side_effect=lambda: fake_db_session(session),
        ),
        patch(
            "orchestration.flows.renew_watches_flow.GmailService"
        ) as mock_gmail,
        patch(
            "orchestration.flows.renew_watches_flow.AccountService"
        ) as mock_account_service,
    ):
        # First account raises, second succeeds.
        mock_gmail.watch_mailbox_for_updates = AsyncMock(
            side_effect=[
                RuntimeError("boom"),
                {"historyId": "777"},
            ]
        )
        mock_account_service.get_account_by_user_and_provider = AsyncMock(
            return_value=MagicMock()
        )
        mock_account_service.update_history_id = AsyncMock()

        await renew_gmail_watches.fn()

    # Both accounts attempted; the second still advanced despite the first failing.
    assert mock_gmail.watch_mailbox_for_updates.call_count == 2
    assert mock_account_service.update_history_id.call_count == 1
    assert mock_account_service.update_history_id.call_args.args[2] == "777"
