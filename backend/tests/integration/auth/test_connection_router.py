from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from auth.models.connected_account import ConnectedAccount
from auth.scopes import DRIVE_FILE_SCOPE, GOOGLE_SCOPES
from core.config_loader import settings


# ---------------------------------------------------------------------------
# GET /api/connection/status
# ---------------------------------------------------------------------------


async def test_connection_status_requires_auth(client):
    response = await client.get("/api/connection/status")
    assert response.status_code == 401


async def test_connection_status_no_accounts(client, auth_headers):
    response = await client.get("/api/connection/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "integrations" in body
    assert all(not i["is_connected"] for i in body["integrations"])


async def test_connection_status_with_google_account(
    client, db_session, test_user, auth_headers, test_connected_account
):
    response = await client.get("/api/connection/status", headers=auth_headers)
    assert response.status_code == 200

    integrations = response.json()["integrations"]
    google = next((i for i in integrations if i["provider"] == "google"), None)

    assert google is not None
    assert google["is_connected"] is True
    assert google["needs_reconnect"] is False
    assert google["email"] == test_user.email


async def test_connection_status_needs_reconnect_when_no_refresh_token(
    client, db_session, test_user, auth_headers
):
    account = ConnectedAccount(
        user_id=test_user.id,
        provider="google",
        provider_account_id=f"goog_{uuid4()}",
        is_connected=True,
        access_token="some_access",
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        metadata_account={"email": test_user.email},
    )
    db_session.add(account)
    await db_session.flush()

    response = await client.get("/api/connection/status", headers=auth_headers)
    assert response.status_code == 200

    integrations = response.json()["integrations"]
    google = next((i for i in integrations if i["provider"] == "google"), None)

    assert google is not None
    assert google["is_connected"] is True
    assert google["needs_reconnect"] is True


# ---------------------------------------------------------------------------
# Scope drift — a grant is never widened on refresh, so an account connected
# before a scope was added must be flagged for reconnect instead of failing
# later with an invisible 403.
# ---------------------------------------------------------------------------


async def _make_account(db_session, test_user, **overrides) -> ConnectedAccount:
    account = ConnectedAccount(
        user_id=test_user.id,
        provider="google",
        provider_account_id=f"goog_{uuid4()}",
        is_connected=True,
        access_token="some_access",
        refresh_token="some_refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        metadata_account={"email": test_user.email},
        **overrides,
    )
    db_session.add(account)
    await db_session.flush()
    return account


def _google(response):
    return next(i for i in response.json()["integrations"] if i["provider"] == "google")


async def test_connection_status_needs_reconnect_when_scope_missing(
    client, db_session, test_user, auth_headers
):
    """An account granted before drive.file was required must be reconnected."""
    stale = " ".join(s for s in GOOGLE_SCOPES if s != DRIVE_FILE_SCOPE)
    await _make_account(db_session, test_user, scope=stale)

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    assert _google(response)["needs_reconnect"] is True


async def test_connection_status_no_reconnect_with_full_scopes(
    client, db_session, test_user, auth_headers
):
    await _make_account(db_session, test_user, scope=" ".join(GOOGLE_SCOPES))

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    assert _google(response)["needs_reconnect"] is False


async def test_connection_status_null_scope_does_not_nag(
    client, db_session, test_user, auth_headers
):
    """A null scope column predates us recording grants — we can't tell what it
    covers, and nagging every legacy account is worse than the 403 this prevents."""
    await _make_account(db_session, test_user, scope=None)

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    assert _google(response)["needs_reconnect"] is False


# ---------------------------------------------------------------------------
# Slack — a second provider whose bot token has no refresh token and no expiry,
# and which is hidden entirely on deployments that haven't configured it.
# ---------------------------------------------------------------------------


@pytest.fixture
def slack_configured(monkeypatch):
    monkeypatch.setattr(settings, "slack_oauth_client_id", "test-slack-client")
    monkeypatch.setattr(settings, "slack_oauth_client_secret", "test-slack-secret")
    monkeypatch.setattr(
        settings,
        "slack_oauth_redirect_uri",
        "http://testserver/api/auth/callback/slack",
    )


async def _make_slack_account(db_session, test_user, **overrides) -> ConnectedAccount:
    fields = {
        "user_id": test_user.id,
        "provider": "slack",
        "provider_account_id": f"T{uuid4().hex[:8]}",
        "is_connected": True,
        "access_token": "enc-xoxb",
        "refresh_token": None,
        "token_expires_at": None,
        "scope": "chat:write",
        "metadata_account": {"team_name": "Acme Workspace"},
    }
    fields.update(overrides)
    account = ConnectedAccount(**fields)
    db_session.add(account)
    await db_session.flush()
    return account


def _slack(response):
    return next(
        (i for i in response.json()["integrations"] if i["provider"] == "slack"), None
    )


async def test_slack_hidden_when_not_configured(client, auth_headers):
    """Default deployment has no Slack env — the card must not render at all."""
    response = await client.get("/api/connection/status", headers=auth_headers)
    assert response.status_code == 200
    assert _slack(response) is None


async def test_slack_shown_when_configured_without_account(
    client, auth_headers, slack_configured
):
    response = await client.get("/api/connection/status", headers=auth_headers)
    assert response.status_code == 200
    slack = _slack(response)
    assert slack is not None
    assert slack["is_connected"] is False
    assert slack["needs_reconnect"] is False


async def test_slack_healthy_without_refresh_token(
    client, db_session, test_user, auth_headers, slack_configured
):
    """A bot token legitimately has no refresh token — that must not read as broken."""
    await _make_slack_account(db_session, test_user)

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    slack = _slack(response)
    assert slack["is_connected"] is True
    assert slack["needs_reconnect"] is False
    assert slack["email"] == "Acme Workspace"


async def test_slack_needs_reconnect_when_access_token_cleared(
    client, db_session, test_user, auth_headers, slack_configured
):
    """The task nulls access_token on token_revoked — that is the reconnect signal."""
    await _make_slack_account(db_session, test_user, access_token=None)

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    assert _slack(response)["needs_reconnect"] is True


async def test_slack_needs_reconnect_when_scope_missing(
    client, db_session, test_user, auth_headers, slack_configured
):
    await _make_slack_account(db_session, test_user, scope="im:write")

    response = await client.get("/api/connection/status", headers=auth_headers)

    assert response.status_code == 200
    assert _slack(response)["needs_reconnect"] is True
