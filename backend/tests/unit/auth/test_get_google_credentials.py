"""Unit tests for AuthService.get_google_credentials.

This is the only code path that can destroy a user's stored Google credentials
(the ``invalid_grant`` branch wipes both tokens and marks the account
disconnected), and it owns token decryption plus the naive/aware expiry
normalisation that google-auth's ``creds.valid`` comparison depends on.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from google.auth.exceptions import RefreshError

from auth.services.auth_service import AuthService

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def db():
    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def account():
    """A connected Google account with an aware expiry one hour out."""
    acc = MagicMock()
    acc.access_token = "encrypted-access"
    acc.refresh_token = "encrypted-refresh"
    acc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    acc.is_connected = True
    return acc


def _patch_deps(account, creds):
    """Patch the three collaborators get_google_credentials reaches for."""
    account_service = MagicMock()
    account_service.get_account_by_user_and_provider = AsyncMock(return_value=account)
    account_service.refresh_tokens = AsyncMock()

    return (
        patch("auth.services.auth_service.AccountService", account_service),
        patch(
            "auth.services.auth_service.decrypt_token",
            side_effect=lambda t: f"decrypted:{t}",
        ),
        patch("auth.services.auth_service.Credentials", return_value=creds),
        account_service,
    )


def make_creds(valid=True, token="access-token", refresh_token="refresh-token"):
    creds = MagicMock()
    creds.valid = valid
    creds.token = token
    creds.refresh_token = refresh_token
    creds.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    creds.refresh = MagicMock()
    return creds


# ---------------------------------------------------------------------------
# Guard clauses
# ---------------------------------------------------------------------------


async def test_no_connected_account_raises_404(db, user_id):
    account_service = MagicMock()
    account_service.get_account_by_user_and_provider = AsyncMock(return_value=None)

    with patch("auth.services.auth_service.AccountService", account_service):
        with pytest.raises(HTTPException) as exc:
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert exc.value.status_code == 404


async def test_missing_token_expiry_raises_500(db, user_id, account):
    account.token_expires_at = None
    account_service = MagicMock()
    account_service.get_account_by_user_and_provider = AsyncMock(return_value=account)

    with patch("auth.services.auth_service.AccountService", account_service):
        with pytest.raises(HTTPException) as exc:
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_valid_credentials_are_returned_without_refreshing(db, user_id, account):
    creds = make_creds(valid=True)
    p_acct, p_decrypt, p_creds, account_service = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        result = await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert result is creds
    creds.refresh.assert_not_called()
    account_service.refresh_tokens.assert_not_awaited()


async def test_stored_tokens_are_decrypted_before_use(db, user_id, account):
    creds = make_creds(valid=True)
    p_acct, p_decrypt, _, _ = _patch_deps(account, creds)

    with (
        p_acct,
        p_decrypt,
        patch(
            "auth.services.auth_service.Credentials", return_value=creds
        ) as credentials_cls,
    ):
        await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    kwargs = credentials_cls.call_args.kwargs
    assert kwargs["token"] == "decrypted:encrypted-access"
    assert kwargs["refresh_token"] == "decrypted:encrypted-refresh"


async def test_expired_credentials_are_refreshed_and_persisted(db, user_id, account):
    creds = make_creds(valid=False)
    p_acct, p_decrypt, p_creds, account_service = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        result = await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert result is creds
    creds.refresh.assert_called_once()
    account_service.refresh_tokens.assert_awaited_once()
    persisted = account_service.refresh_tokens.await_args.kwargs
    assert persisted["token"] == "access-token"
    assert persisted["refresh_token"] == "refresh-token"
    assert persisted["expiry"] == creds.expiry


# ---------------------------------------------------------------------------
# Expiry normalisation — google-auth compares against a naive UTC datetime, so
# an aware and a naive stored expiry must produce the same value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("aware", [True, False])
async def test_expiry_is_normalised_to_naive_utc(db, user_id, account, aware):
    stored = datetime(2026, 7, 25, 14, 30, tzinfo=timezone.utc)
    account.token_expires_at = stored if aware else stored.replace(tzinfo=None)

    creds = make_creds(valid=True)
    p_acct, p_decrypt, _, _ = _patch_deps(account, creds)

    with (
        p_acct,
        p_decrypt,
        patch(
            "auth.services.auth_service.Credentials", return_value=creds
        ) as credentials_cls,
    ):
        await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    expiry = credentials_cls.call_args.kwargs["expiry"]
    assert expiry.tzinfo is None
    assert expiry == datetime(2026, 7, 25, 14, 30)


async def test_non_utc_expiry_is_converted_not_just_stripped(db, user_id, account):
    # 14:30 at UTC+2 is 12:30 UTC — a naive strip would wrongly keep 14:30.
    account.token_expires_at = datetime(
        2026, 7, 25, 14, 30, tzinfo=timezone(timedelta(hours=2))
    )

    creds = make_creds(valid=True)
    p_acct, p_decrypt, _, _ = _patch_deps(account, creds)

    with (
        p_acct,
        p_decrypt,
        patch(
            "auth.services.auth_service.Credentials", return_value=creds
        ) as credentials_cls,
    ):
        await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert credentials_cls.call_args.kwargs["expiry"] == datetime(2026, 7, 25, 12, 30)


# ---------------------------------------------------------------------------
# Refresh failures
# ---------------------------------------------------------------------------


async def test_invalid_grant_disconnects_account_and_wipes_tokens(db, user_id, account):
    creds = make_creds(valid=False)
    creds.refresh.side_effect = RefreshError("invalid_grant: Token has been revoked.")
    p_acct, p_decrypt, p_creds, account_service = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        with pytest.raises(ValueError, match="GOOGLE_AUTH_EXPIRED"):
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert account.is_connected is False
    assert account.access_token is None
    assert account.refresh_token is None
    db.commit.assert_awaited_once()
    account_service.refresh_tokens.assert_not_awaited()


async def test_expired_token_message_also_disconnects(db, user_id, account):
    creds = make_creds(valid=False)
    creds.refresh.side_effect = RefreshError("Token has been expired or revoked.")
    p_acct, p_decrypt, p_creds, _ = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        with pytest.raises(ValueError, match="GOOGLE_AUTH_EXPIRED"):
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert account.is_connected is False


async def test_other_refresh_error_raises_401_and_keeps_account_connected(
    db, user_id, account
):
    creds = make_creds(valid=False)
    creds.refresh.side_effect = RefreshError("temporary upstream failure")
    p_acct, p_decrypt, p_creds, _ = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        with pytest.raises(HTTPException) as exc:
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert exc.value.status_code == 401
    # The account must survive a transient failure untouched.
    assert account.is_connected is True
    assert account.access_token == "encrypted-access"
    db.commit.assert_not_awaited()


async def test_unexpected_exception_raises_401(db, user_id, account):
    creds = make_creds(valid=False)
    creds.refresh.side_effect = RuntimeError("socket exploded")
    p_acct, p_decrypt, p_creds, _ = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        with pytest.raises(HTTPException) as exc:
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert exc.value.status_code == 401
    assert account.is_connected is True


async def test_refresh_yielding_no_token_does_not_persist_none(db, user_id, account):
    """Replaces the stripped-under-`-O` assert: a None token must never reach
    AccountService.refresh_tokens, where it would be encrypted and stored."""
    creds = make_creds(valid=False, token=None)
    p_acct, p_decrypt, p_creds, account_service = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        with pytest.raises(HTTPException) as exc:
            await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert exc.value.status_code == 401
    account_service.refresh_tokens.assert_not_awaited()
    # Not an invalid_grant, so the account keeps its stored tokens.
    assert account.access_token == "encrypted-access"


async def test_refresh_skipped_when_no_refresh_token_available(db, user_id, account):
    creds = make_creds(valid=False, refresh_token=None)
    p_acct, p_decrypt, p_creds, account_service = _patch_deps(account, creds)

    with p_acct, p_decrypt, p_creds:
        result = await AuthService.get_google_credentials(db, user_id, "google", SCOPES)

    assert result is creds
    creds.refresh.assert_not_called()
    account_service.refresh_tokens.assert_not_awaited()
