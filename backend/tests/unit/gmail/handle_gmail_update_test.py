"""Unit tests for GmailService.handle_gmail_update — the dropped-notification fix.

handle_gmail_update uses the real ``db_session()`` context manager and several
service collaborators, so everything external is patched. The ConnectedAccount
row is represented by a SimpleNamespace shared between phase 1 (claim/defer) and
phase 2 (drain loop): both ``_acquire_account_locked`` and
``get_account_by_user_and_provider`` return the same object, so attribute
mutations are observable across the whole flow.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
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

    @asynccontextmanager
    async def fake_db_session():
        yield AsyncMock()

    processor_cm = MagicMock()
    processor_instance = MagicMock()
    fetch = AsyncMock()
    processor_instance.fetch_and_process = fetch
    processor_cm.return_value.__aenter__ = AsyncMock(return_value=processor_instance)
    processor_cm.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{MODULE}.db_session", fake_db_session), patch(
        f"{MODULE}.UserService.get_by_email", new_callable=AsyncMock, return_value=user
    ), patch.object(
        GmailService, "_acquire_account_locked", new_callable=AsyncMock, return_value=account
    ), patch(
        f"{MODULE}.AccountService.get_account_by_user_and_provider",
        new_callable=AsyncMock,
        return_value=account,
    ), patch(
        f"{MODULE}.AuthService.get_google_credentials",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ), patch(
        f"{MODULE}.GmailHistoryProcessor", processor_cm
    ):
        yield SimpleNamespace(account=account, fetch=fetch)


async def test_owner_no_pending_fetches_once_and_releases(patched):
    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 1
    # baseline advanced to the high-water mark (this notification's id)
    assert patched.account.last_synced_history_id == "150"
    assert patched.account.last_synced_started_at is None  # lock released
    assert patched.account.sync_pending is False


async def test_pending_set_midrun_triggers_second_drain(patched):
    # Simulate notification B landing during A's fetch: first fetch flips the
    # pending flag, second fetch does nothing.
    async def side_effect(_baseline):
        if patched.fetch.call_count == 1:
            patched.account.sync_pending = True

    patched.fetch.side_effect = side_effect

    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 2
    assert patched.account.sync_pending is False
    assert patched.account.last_synced_started_at is None


async def test_deferred_when_sync_in_progress(patched):
    # A sync started just now → this notification must defer, not fetch.
    patched.account.last_synced_started_at = datetime.now(timezone.utc)

    await GmailService.handle_gmail_update("user@example.com", "150")

    patched.fetch.assert_not_called()
    assert patched.account.sync_pending is True
    assert patched.account.latest_observed_history_id == "150"  # still recorded


async def test_stale_lock_is_taken_over(patched):
    # last_synced_started_at older than 1 minute → not "in progress", take over.
    patched.account.last_synced_started_at = datetime.now(timezone.utc) - timedelta(
        minutes=5
    )

    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 1
    assert patched.account.last_synced_started_at is None


async def test_http_error_releases_lock_but_keeps_pending(patched):
    # A deferral lands during the fetch, then the fetch fails. The pending flag
    # must survive so the missed window is retried later.
    async def side_effect(_baseline):
        patched.account.sync_pending = True
        raise HttpError(resp=MagicMock(status=500), content=b"boom")

    patched.fetch.side_effect = side_effect

    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.account.last_synced_started_at is None  # released
    assert patched.account.sync_pending is True  # preserved for retry


async def test_generic_error_releases_lock_but_keeps_pending(patched):
    async def side_effect(_baseline):
        patched.account.sync_pending = True
        raise RuntimeError("kaboom")

    patched.fetch.side_effect = side_effect

    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.account.last_synced_started_at is None
    assert patched.account.sync_pending is True


async def test_stale_history_404_resets_baseline(patched):
    # startHistoryId too old → Gmail 404. Adopt the high-water mark so future
    # notifications resync forward instead of failing on the dead id forever.
    async def side_effect(_baseline):
        raise HttpError(resp=MagicMock(status=404), content=b"too old")

    patched.fetch.side_effect = side_effect

    await GmailService.handle_gmail_update("user@example.com", "150")

    assert patched.fetch.call_count == 1  # no infinite retry loop
    assert patched.account.last_synced_history_id == "150"  # baseline advanced
    assert patched.account.last_synced_started_at is None  # lock released
    assert patched.account.sync_pending is False


async def test_none_baseline_adopts_latest_and_skips_fetch(patched):
    # Account never completed a watch → baseline None must not hit the API.
    patched.account.last_synced_history_id = None

    await GmailService.handle_gmail_update("user@example.com", "150")

    patched.fetch.assert_not_called()
    assert patched.account.last_synced_history_id == "150"
    assert patched.account.last_synced_started_at is None
