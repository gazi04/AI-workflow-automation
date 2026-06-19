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

def test_valid_payload_returns_success(client):
    with patch("gmail.routes.webhook_router.GmailService.handle_gmail_update"):
        response = client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_missing_email_address_ignored(client):
    data = base64.b64encode(json.dumps({"historyId": "99999"}).encode()).decode()
    response = client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": data}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_history_id_ignored(client):
    data = base64.b64encode(json.dumps({"emailAddress": "user@gmail.com"}).encode()).decode()
    response = client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": data}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_malformed_base64_acked_not_retried(client):
    # Malformed payloads return 200 so Pub/Sub doesn't retry forever.
    response = client.post(
        "/api/webhooks/gmail",
        json={"message": {"data": "!!!not-base64!!!"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_message_key_acked_not_retried(client):
    # Same: bad structure is acked, not retried.
    response = client.post("/api/webhooks/gmail", json={"unexpected": "payload"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_handle_update_enqueued_as_background_task(client):
    """handle_gmail_update is dispatched via BackgroundTasks, not called synchronously."""
    call_log = []

    def fake_handle(email, history_id):
        call_log.append((email, history_id))

    with patch("gmail.routes.webhook_router.GmailService.handle_gmail_update", fake_handle):
        response = client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "12345"),
        )

    assert response.status_code == 200
    # TestClient runs background tasks synchronously, so call_log will be populated
    assert len(call_log) == 1
    assert call_log[0] == ("user@gmail.com", "12345")


# ---------------------------------------------------------------------------
# POST /api/webhooks/gmail — OIDC verification
# ---------------------------------------------------------------------------

FAKE_AUDIENCE = "https://api.example.com/api/webhooks/gmail"


def test_missing_bearer_token_returns_401(client):
    with patch("gmail.routes.webhook_router.settings") as mock_settings:
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
        )
    assert response.status_code == 401


def test_invalid_oidc_token_returns_401(client):
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")),
    ):
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
            headers={"Authorization": "Bearer fake.token.here"},
        )
    assert response.status_code == 401


def test_valid_oidc_token_allows_request(client):
    with (
        patch("gmail.routes.webhook_router.settings") as mock_settings,
        patch("gmail.routes.webhook_router.google_id_token.verify_oauth2_token", return_value={"sub": "service-account@project.iam.gserviceaccount.com"}),
        patch("gmail.routes.webhook_router.GmailService.handle_gmail_update"),
    ):
        mock_settings.google_pubsub_audience = FAKE_AUDIENCE
        response = client.post(
            "/api/webhooks/gmail",
            json=make_pubsub_payload("user@gmail.com", "99999"),
            headers={"Authorization": "Bearer valid.token.here"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
