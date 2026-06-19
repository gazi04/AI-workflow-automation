"""Unit tests for GmailService.handle_gmail_update — the dropped-notification fix.

handle_gmail_update uses the real ``db_session()`` context manager and several
service collaborators, so everything external is patched. The ConnectedAccount
row is represented by a SimpleNamespace shared between phase 1 (claim/defer) and
phase 2 (drain loop): both ``_acquire_account_locked`` and
``get_account_by_user_and_provider`` return the same object, so attribute
mutations are observable across the whole flow.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from googleapiclient.errors import HttpError

from gmail.services.gmail_service import GmailService

MODULE = "gmail.services.gmail_service"


@pytest.fixture
def account():
    return SimpleNamespace(
        last_synced_history_id="100",
        last_synced_started_at=None,
        sync_pending=False,
        latest_observed_history_id=None,
    )


@pytest.fixture
def patched(account):
    """Patch every collaborator of handle_gmail_update around one account row."""
    user = SimpleNamespace(id=uuid4())

    @contextmanager
    def fake_db_session():
        yield MagicMock()

    processor_cm = MagicMock()
    fetch = processor_cm.return_value.__enter__.return_value.fetch_and_process

    with patch(f"{MODULE}.db_session", fake_db_session), patch(
        f"{MODULE}.UserService.get_by_email", return_value=user
    ), patch.object(
        GmailService, "_acquire_account_locked", return_value=account
    ), patch(
        f"{MODULE}.AccountService.get_account_by_user_and_provider",
        return_value=account,
    ), patch(
        f"{MODULE}.AuthService.get_google_credentials", return_value=MagicMock()
    ), patch(
        f"{MODULE}.GmailHistoryProcessor", processor_cm
    ):
        yield SimpleNamespace(account=account, fetch=fetch)


def test_owner_no_pending_fetches_once_and_releases(patched):
    GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 1
    # baseline advanced to the high-water mark (this notification's id)
    assert patched.account.last_synced_history_id == "150"
    assert patched.account.last_synced_started_at is None  # lock released
    assert patched.account.sync_pending is False


def test_pending_set_midrun_triggers_second_drain(patched):
    # Simulate notification B landing during A's fetch: first fetch flips the
    # pending flag, second fetch does nothing.
    def side_effect(_baseline):
        if patched.fetch.call_count == 1:
            patched.account.sync_pending = True

    patched.fetch.side_effect = side_effect

    GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 2
    assert patched.account.sync_pending is False
    assert patched.account.last_synced_started_at is None


def test_deferred_when_sync_in_progress(patched):
    # A sync started just now → this notification must defer, not fetch.
    patched.account.last_synced_started_at = datetime.now(timezone.utc)

    GmailService.handle_gmail_update("user@example.com", "150")

    patched.fetch.assert_not_called()
    assert patched.account.sync_pending is True
    assert patched.account.latest_observed_history_id == "150"  # still recorded


def test_stale_lock_is_taken_over(patched):
    # last_synced_started_at older than 1 minute → not "in progress", take over.
    patched.account.last_synced_started_at = datetime.now(timezone.utc) - timedelta(
        minutes=5
    )

    GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 1
    assert patched.account.last_synced_started_at is None


def test_http_error_releases_lock_but_keeps_pending(patched):
    # A deferral lands during the fetch, then the fetch fails. The pending flag
    # must survive so the missed window is retried later.
    def side_effect(_baseline):
        patched.account.sync_pending = True
        raise HttpError(resp=MagicMock(status=500), content=b"boom")

    patched.fetch.side_effect = side_effect

    GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.account.last_synced_started_at is None  # released
    assert patched.account.sync_pending is True  # preserved for retry


def test_generic_error_releases_lock_but_keeps_pending(patched):
    def side_effect(_baseline):
        patched.account.sync_pending = True
        raise RuntimeError("kaboom")

    patched.fetch.side_effect = side_effect

    GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.account.last_synced_started_at is None
    assert patched.account.sync_pending is True
