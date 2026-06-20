from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from auth.utils import create_access_token


# ---------------------------------------------------------------------------
# GET /api/auth/protected
# ---------------------------------------------------------------------------

def test_protected_with_valid_jwt(client, test_user, auth_headers):
    response = client.get("/api/auth/protected", headers=auth_headers)
    assert response.status_code == 200
    assert test_user.email in response.json()["message"]


def test_protected_with_no_auth_header(client):
    response = client.get("/api/auth/protected")
    assert response.status_code == 401


def test_protected_with_invalid_jwt(client):
    response = client.get("/api/auth/protected", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert response.status_code == 401


def test_protected_with_malformed_bearer(client):
    response = client.get("/api/auth/protected", headers={"Authorization": "Token abc"})
    assert response.status_code == 401


def test_protected_with_expired_access_token(client):
    expired_token = create_access_token({"sub": str(uuid4())}, expires_delta=timedelta(seconds=-1))
    response = client.get("/api/auth/protected", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_protected_with_nonexistent_user(client):
    token = create_access_token({"sub": str(uuid4()), "email": "ghost@test.com"})
    response = client.get("/api/auth/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

def test_refresh_with_valid_token_returns_new_pair(client, test_user, test_refresh_token):
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        }
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": test_refresh_token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "new_access"
    assert body["refresh_token"] == "new_refresh"
    assert body["token_type"] == "bearer"


def test_refresh_with_invalid_token_returns_401(client):
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

    assert response.status_code == 401


def test_refresh_with_expired_token_returns_401(client, test_user, expired_refresh_token):
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_refresh_token},
        )

    assert response.status_code == 401


def test_refresh_with_revoked_token_returns_401(client, test_user, revoked_refresh_token):
    with patch("auth.routes.auth_router.TokenService.refresh_token") as mock_refresh:
        mock_refresh.return_value = None
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": revoked_refresh_token},
        )

    assert response.status_code == 401
