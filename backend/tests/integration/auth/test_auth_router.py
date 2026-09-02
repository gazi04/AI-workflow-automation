from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import select

from auth.models.connected_account import ConnectedAccount
from auth.models.oauth_state import OAuthState
from auth.routes.auth_router import SLACK_AUTHORIZE_URL
from auth.utils import create_access_token
from core.config_loader import settings
from core.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from core.crypto import decrypt_token


# ---------------------------------------------------------------------------
# GET /api/auth/protected
# ---------------------------------------------------------------------------


async def test_protected_with_valid_jwt(client, test_user, auth_headers):
    response = await client.get("/api/auth/protected", headers=auth_headers)
    assert response.status_code == 200
    assert test_user.email in response.json()["message"]


async def test_protected_with_no_auth_header(client):
    response = await client.get("/api/auth/protected")
    assert response.status_code == 401


async def test_protected_with_invalid_jwt(client):
    response = await client.get(
        "/api/auth/protected", headers={"Authorization": "Bearer not.a.valid.jwt"}
    )
    assert response.status_code == 401


async def test_protected_with_malformed_bearer(client):
    response = await client.get(
        "/api/auth/protected", headers={"Authorization": "Token abc"}
    )
    assert response.status_code == 401


async def test_protected_with_expired_access_token(client):
    expired_token = create_access_token(
        {"sub": str(uuid4())}, expires_delta=timedelta(seconds=-1)
    )
    response = await client.get(
        "/api/auth/protected", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


async def test_protected_with_nonexistent_user(client):
    token = create_access_token({"sub": str(uuid4()), "email": "ghost@test.com"})
    response = await client.get(
        "/api/auth/protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------


async def test_refresh_with_valid_cookie_sets_new_cookies(
    client, test_user, test_refresh_token, csrf_headers
):
    new_access = create_access_token(
        {"sub": str(test_user.id), "email": test_user.email}
    )
    client.cookies.set(REFRESH_COOKIE, test_refresh_token)

    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = {
            "access_token": new_access,
            "refresh_token": "new_refresh",
        }
        response = await client.post("/api/auth/refresh", headers=csrf_headers)

    assert response.status_code == 200
    assert response.json()["user"]["email"] == test_user.email
    # New tokens are delivered as cookies, never in the body.
    assert response.cookies[ACCESS_COOKIE] == new_access
    assert response.cookies[REFRESH_COOKIE] == "new_refresh"


async def test_refresh_with_missing_cookie_returns_401(client, csrf_headers):
    response = await client.post("/api/auth/refresh", headers=csrf_headers)
    assert response.status_code == 401


async def test_refresh_with_invalid_token_returns_401(client, csrf_headers):
    client.cookies.set(REFRESH_COOKIE, "invalid-token")
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = await client.post("/api/auth/refresh", headers=csrf_headers)

    assert response.status_code == 401


async def test_refresh_with_expired_token_returns_401(
    client, test_user, expired_refresh_token, csrf_headers
):
    client.cookies.set(REFRESH_COOKIE, expired_refresh_token)
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = await client.post("/api/auth/refresh", headers=csrf_headers)

    assert response.status_code == 401


async def test_refresh_with_revoked_token_returns_401(
    client, test_user, revoked_refresh_token, csrf_headers
):
    client.cookies.set(REFRESH_COOKIE, revoked_refresh_token)
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = await client.post("/api/auth/refresh", headers=csrf_headers)

    assert response.status_code == 401


async def test_refresh_without_csrf_token_returns_403(client, test_refresh_token):
    """The CSRF middleware gates the refresh route before auth runs."""
    client.cookies.set(REFRESH_COOKIE, test_refresh_token)
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Slack connect / callback — a connect flow for an already-authenticated user.
# Unlike the Google callback it mints no app tokens and never creates a user.
# ---------------------------------------------------------------------------


_SLACK_OK = {
    "ok": True,
    "access_token": "xoxb-real-secret",
    "token_type": "bot",
    "scope": "chat:write",
    "bot_user_id": "U0BOT",
    "team": {"id": "T0ACME", "name": "Acme Workspace"},
    "authed_user": {"id": "U0USER"},
}


@pytest.fixture
def slack_configured(monkeypatch):
    monkeypatch.setattr(settings, "slack_oauth_client_id", "test-slack-client")
    monkeypatch.setattr(settings, "slack_oauth_client_secret", "test-slack-secret")
    monkeypatch.setattr(
        settings,
        "slack_oauth_redirect_uri",
        "http://testserver/api/auth/callback/slack",
    )


@pytest.fixture
def slack_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "slack_oauth_client_id", None)
    monkeypatch.setattr(settings, "slack_oauth_client_secret", None)
    monkeypatch.setattr(settings, "slack_oauth_redirect_uri", None)


async def _start_slack_connect(client, auth_headers) -> str:
    """Hit /connect/slack and return the freshly created state token."""
    response = await client.get("/api/auth/connect/slack", headers=auth_headers)
    assert response.status_code == 200
    auth_url = response.json()["auth_url"]
    return parse_qs(urlparse(auth_url).query)["state"][0]


async def test_connect_slack_requires_auth(client, slack_configured):
    response = await client.get("/api/auth/connect/slack")
    assert response.status_code == 401


async def test_connect_slack_returns_503_when_unconfigured(
    client, auth_headers, slack_unconfigured
):
    response = await client.get("/api/auth/connect/slack", headers=auth_headers)
    assert response.status_code == 503


async def test_connect_slack_returns_authorize_url_and_persists_state(
    client, db_session, test_user, auth_headers, slack_configured
):
    response = await client.get("/api/auth/connect/slack", headers=auth_headers)
    assert response.status_code == 200

    auth_url = response.json()["auth_url"]
    assert auth_url.startswith(SLACK_AUTHORIZE_URL)
    query = parse_qs(urlparse(auth_url).query)
    assert query["scope"] == ["chat:write"]
    state = query["state"][0]

    row = (
        await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    ).scalar_one()
    assert row.provider == "slack"
    assert row.user_id == test_user.id


async def test_callback_slack_happy_path_creates_connected_account(
    client, db_session, test_user, auth_headers, slack_configured
):
    state = await _start_slack_connect(client, auth_headers)

    with patch(
        "auth.routes.auth_router._exchange_slack_code", return_value=dict(_SLACK_OK)
    ):
        response = await client.get(
            f"/api/auth/callback/slack?code=abc123&state={state}"
        )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == (
        f"{settings.frontend_url}/dashboard/integrations"
    )

    account = (
        await db_session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == test_user.id,
                ConnectedAccount.provider == "slack",
            )
        )
    ).scalar_one()
    assert account.is_connected is True
    assert account.refresh_token is None
    assert account.token_expires_at is None
    assert account.scope == "chat:write"
    assert account.provider_account_id == "T0ACME"
    assert account.metadata_account["team_name"] == "Acme Workspace"
    # Token is stored Fernet-encrypted, never in the clear.
    assert account.access_token != "xoxb-real-secret"
    assert decrypt_token(account.access_token) == "xoxb-real-secret"


async def test_callback_slack_unknown_state_redirects_with_error(
    client, db_session, test_user, slack_configured
):
    with patch("auth.routes.auth_router._exchange_slack_code") as exchange:
        response = await client.get(
            "/api/auth/callback/slack?code=abc&state=not-a-real-state"
        )

    assert response.status_code in (302, 307)
    assert "error=slack_failed" in response.headers["location"]
    exchange.assert_not_called()

    accounts = (
        (
            await db_session.execute(
                select(ConnectedAccount).where(ConnectedAccount.provider == "slack")
            )
        )
        .scalars()
        .all()
    )
    assert accounts == []


async def test_callback_slack_rejects_non_slack_state(
    client, db_session, test_user, slack_configured
):
    """A Google state row must not be usable to complete a Slack connect."""
    google_state = OAuthState(
        state=f"g-{uuid4()}",
        provider=None,
        user_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(google_state)
    await db_session.flush()

    with patch("auth.routes.auth_router._exchange_slack_code") as exchange:
        response = await client.get(
            f"/api/auth/callback/slack?code=abc&state={google_state.state}"
        )

    assert response.status_code in (302, 307)
    assert "error=slack_failed" in response.headers["location"]
    exchange.assert_not_called()


async def test_callback_slack_exchange_failure_redirects_with_error(
    client, db_session, test_user, auth_headers, slack_configured
):
    state = await _start_slack_connect(client, auth_headers)

    with patch(
        "auth.routes.auth_router._exchange_slack_code",
        return_value={"ok": False, "error": "invalid_code"},
    ):
        response = await client.get(f"/api/auth/callback/slack?code=bad&state={state}")

    assert response.status_code in (302, 307)
    assert "error=slack_failed" in response.headers["location"]

    accounts = (
        (
            await db_session.execute(
                select(ConnectedAccount).where(
                    ConnectedAccount.user_id == test_user.id,
                    ConnectedAccount.provider == "slack",
                )
            )
        )
        .scalars()
        .all()
    )
    assert accounts == []
