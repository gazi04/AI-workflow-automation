import base64
import json
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pubsub_payload(email: str, history_id: str) -> dict:
    data = base64.b64encode(
        json.dumps({"emailAddress": email, "historyId": history_id}).encode()
    ).decode()
    return {"message": {"data": data}}


# ---------------------------------------------------------------------------
# POST /api/webhooks/gmail — payload parsing (OIDC disabled in test env)
# ---------------------------------------------------------------------------

async def test_valid_payload_returns_success(client):
    with patch("gmail.routes.webhook_router.GmailService.handle_gmail_update"):
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_missing_email_address_ignored(client):
    data = base64.b64encode(json.dumps({"historyId": "99999"}).encode()).decode()
    response = await client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": data}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_missing_history_id_ignored(client):
    data = base64.b64encode(json.dumps({"emailAddress": "user@gmail.com"}).encode()).decode()
    response = await client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": data}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_malformed_base64_acked_not_retried(client):
    # Malformed payloads return 200 so Pub/Sub doesn't retry forever.
    response = await client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": "!!!not-base64!!!"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_missing_message_key_acked_not_retried(client):
    # Same: bad structure is acked, not retried.
    response = await client.post("/api/webhooks/gmail", json={"unexpected": "payload"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_handle_update_enqueued_as_background_task(client):
    """handle_gmail_update is dispatched via BackgroundTasks, not called synchronously."""
    call_log = []

    async def fake_handle(email, history_id):
        call_log.append((email, history_id))

    with patch("gmail.routes.webhook_router.GmailService.handle_gmail_update", fake_handle):
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "12345"),
        )

    assert response.status_code == 200
    # AsyncClient/ASGITransport still runs background tasks within the same
    # request lifecycle, so call_log will be populated.
    assert len(call_log) == 1
    assert call_log[0] == ("user@gmail.com", "12345")


# ---------------------------------------------------------------------------
# POST /api/webhooks/gmail — OIDC verification
# ---------------------------------------------------------------------------

FAKE_AUDIENCE = "https://api.example.com/api/webhooks/gmail"


async def test_missing_bearer_token_returns_401(client):
    with patch("gmail.routes.webhook_router.settings") as mock_settings:
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 401


async def test_invalid_oidc_token_returns_401(client):
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")),
    ):
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
            headers={"Authorization": "Bearer fake.token.here"},
        )
    assert response.status_code == 401


async def test_valid_oidc_token_allows_request(client):
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.google_id_token.verify_oauth2_token", return_value={"sub": "service-account@project.iam.gserviceaccount.com"}),
        patch("gmail.routes.webhook_router.GmailService.handle_gmail_update"),
    ):
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
            headers={"Authorization": "Bearer valid.token.here"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_missing_audience_fails_closed_when_required(client):
    """No audience + require_pubsub_oidc on → reject (503), never process."""
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.GmailService.handle_gmail_update") as mock_handle,
    ):
        mock_settings.google_pubsub_audience = None
        mock_settings.require_pubsub_oidc = True
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 503
    mock_handle.assert_not_called()


async def test_missing_audience_bypass_allowed_when_not_required(client):
    """No audience + require_pubsub_oidc off → explicit dev bypass still works."""
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.GmailService.handle_gmail_update"),
    ):
        mock_settings.google_pubsub_audience = None
        mock_settings.require_pubsub_oidc = False
        response = await client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
