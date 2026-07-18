from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from auth.utils import create_access_token
from core.cookies import ACCESS_COOKIE, REFRESH_COOKIE


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
    response = await client.get("/api/auth/protected", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert response.status_code == 401


async def test_protected_with_malformed_bearer(client):
    response = await client.get("/api/auth/protected", headers={"Authorization": "Token abc"})
    assert response.status_code == 401


async def test_protected_with_expired_access_token(client):
    expired_token = create_access_token({"sub": str(uuid4())}, expires_delta=timedelta(seconds=-1))
    response = await client.get("/api/auth/protected", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


async def test_protected_with_nonexistent_user(client):
    token = create_access_token({"sub": str(uuid4()), "email": "ghost@test.com"})
    response = await client.get("/api/auth/protected", headers={"Authorization": f"Bearer {token}"})
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
