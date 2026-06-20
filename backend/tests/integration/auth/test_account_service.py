from datetime import datetime, timezone, timedelta
from uuid import uuid4

from auth.models.connected_account import ConnectedAccount
from auth.services.account_service import AccountService


# ---------------------------------------------------------------------------
# get_account_by_user_and_provider
# ---------------------------------------------------------------------------

def test_get_account_found(db_session, test_user, test_connected_account):
    result = AccountService.get_account_by_user_and_provider(db_session, test_user.id, "google")
    assert result is not None
    assert result.id == test_connected_account.id


def test_get_account_not_found_wrong_user(db_session, test_connected_account):
    result = AccountService.get_account_by_user_and_provider(db_session, uuid4(), "google")
    assert result is None


def test_get_account_not_found_wrong_provider(db_session, test_user, test_connected_account):
    result = AccountService.get_account_by_user_and_provider(db_session, test_user.id, "slack")
    assert result is None


# ---------------------------------------------------------------------------
# get_all_user_accounts
# ---------------------------------------------------------------------------

def test_get_all_user_accounts_empty(db_session, test_user):
    result = AccountService.get_all_user_accounts(db_session, test_user.id)
    assert result == []


def test_get_all_user_accounts_returns_connected_account(db_session, test_user, test_connected_account):
    result = AccountService.get_all_user_accounts(db_session, test_user.id)
    assert len(result) == 1
    assert result[0].id == test_connected_account.id


def test_get_all_user_accounts_excludes_other_users(db_session, test_connected_account):
    result = AccountService.get_all_user_accounts(db_session, uuid4())
    assert result == []


# ---------------------------------------------------------------------------
# refresh_tokens
# ---------------------------------------------------------------------------

def test_refresh_tokens_updates_access_token(db_session, test_user, test_connected_account):
    new_token = "new_access_token_xyz"
    new_expiry = datetime.now(timezone.utc) + timedelta(hours=2)

    updated = AccountService.refresh_tokens(
        db_session,
        token=new_token,
        expiry=new_expiry,
        account=test_connected_account,
    )

    assert updated.access_token == new_token
    assert updated.token_expires_at == new_expiry


def test_refresh_tokens_updates_refresh_token_when_provided(db_session, test_user, test_connected_account):
    new_refresh = "new_refresh_token_abc"

    updated = AccountService.refresh_tokens(
        db_session,
        token="new_access",
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        account=test_connected_account,
        refresh_token=new_refresh,
    )

    assert updated.refresh_token == new_refresh


def test_refresh_tokens_preserves_refresh_token_when_not_provided(db_session, test_user, test_connected_account):
    original_refresh = test_connected_account.refresh_token

    updated = AccountService.refresh_tokens(
        db_session,
        token="new_access",
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        account=test_connected_account,
    )

    assert updated.refresh_token == original_refresh


# ---------------------------------------------------------------------------
# update_history_id
# ---------------------------------------------------------------------------

def test_update_history_id(db_session, test_user, test_connected_account):
    new_id = "history_777"
    updated = AccountService.update_history_id(db_session, test_connected_account, new_id)

    assert updated.last_synced_history_id == new_id

    fetched = db_session.query(ConnectedAccount).filter_by(id=test_connected_account.id).first()
    assert fetched.last_synced_history_id == new_id


# ---------------------------------------------------------------------------
# set_sync_pending
# ---------------------------------------------------------------------------

def test_set_sync_pending_toggles(db_session, test_connected_account):
    assert test_connected_account.sync_pending is False

    AccountService.set_sync_pending(db_session, test_connected_account, True)
    assert test_connected_account.sync_pending is True

    AccountService.set_sync_pending(db_session, test_connected_account, False)
    assert test_connected_account.sync_pending is False


# ---------------------------------------------------------------------------
# bump_observed_history_id
# ---------------------------------------------------------------------------

def test_bump_observed_history_id_sets_from_none(db_session, test_connected_account):
    assert test_connected_account.latest_observed_history_id is None

    AccountService.bump_observed_history_id(db_session, test_connected_account, "100")
    assert test_connected_account.latest_observed_history_id == "100"


def test_bump_observed_history_id_advances_on_larger(db_session, test_connected_account):
    AccountService.bump_observed_history_id(db_session, test_connected_account, "100")
    AccountService.bump_observed_history_id(db_session, test_connected_account, "200")
    assert test_connected_account.latest_observed_history_id == "200"


def test_bump_observed_history_id_noop_on_smaller(db_session, test_connected_account):
    AccountService.bump_observed_history_id(db_session, test_connected_account, "100")
    AccountService.bump_observed_history_id(db_session, test_connected_account, "50")
    assert test_connected_account.latest_observed_history_id == "100"
