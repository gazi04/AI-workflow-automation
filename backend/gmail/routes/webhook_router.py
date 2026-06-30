from uuid import UUID

from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from auth.depedencies import get_current_user
from auth.services.account_service import AccountService
from core.config_loader import settings
from core.database import get_db
from core.setup_logging import setup_logger
from gmail.services import GmailService
from orchestration.services import DeploymentService
from user.models.user import User
from workflow.schemas import WorkflowExecutionConfig
from workflow.services import WorkflowService

import base64
import hmac
import json


webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = setup_logger("Webhook router")


def _verify_pubsub_token(request: Request) -> None:
    """Verify the Google Pub/Sub OIDC token in the Authorization header."""
    if not settings.google_pubsub_audience:
        logger.warning(
            "GOOGLE_PUBSUB_AUDIENCE not configured — Pub/Sub OIDC verification disabled"
        )
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Pub/Sub request missing OIDC Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    token = auth_header[len("Bearer ") :]
    try:
        google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.google_pubsub_audience,
        )
    except ValueError as e:
        logger.warning(f"Pub/Sub OIDC token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )


@webhook_router.get("/listen-to-gmail")
async def listen_gmail(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Initiate the webhook to get gmail push notifications"""
    try:
        google_account = AccountService.get_account_by_user_and_provider(
            db, user.id, "google"
        )
        if not google_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Google account connection not found for user.",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve connected account: {e}",
        )

    watch_response = GmailService.watch_mailbox_for_updates(user_id=user.id)

    if watch_response and watch_response.get("historyId"):
        AccountService.update_history_id(
            db, google_account, watch_response["historyId"]
        )


def _find_webhook_trigger_node_id(config: WorkflowExecutionConfig) -> str | None:
    """Return the id of the workflow's webhook trigger start node, if any."""
    for node_id in config.start_node_ids:
        node = config.nodes.get(node_id)
        if node and node.type == "trigger" and node.config.type == "webhook":
            return node_id
    return None


@webhook_router.post("/trigger/{workflow_id}", status_code=status.HTTP_202_ACCEPTED)
async def webhook_trigger(
    workflow_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Generic HTTP webhook entry point. An external caller starts a workflow by
    POSTing here with the workflow's per-workflow secret in the
    `X-Webhook-Secret` header (falling back to a `?secret=` query param).
    """
    workflow = WorkflowService.get_by_id(db, workflow_id)

    # 404 (not 401) on a missing/inactive/non-webhook workflow so we never leak
    # which workflow ids exist or whether one has a webhook trigger.
    if not workflow or not workflow.is_active or not workflow.webhook_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    config = WorkflowExecutionConfig.model_validate(workflow.config)
    node_id = _find_webhook_trigger_node_id(config)
    if node_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    supplied_secret = request.headers.get(
        "X-Webhook-Secret"
    ) or request.query_params.get("secret", "")
    if not supplied_secret or not hmac.compare_digest(
        supplied_secret, workflow.webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    # Strip credential-bearing headers before exposing them to the workflow.
    safe_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("x-webhook-secret", "authorization", "cookie")
    }

    trigger_context = {
        "trigger_context": {
            "webhook_payload": {
                "body": body,
                "headers": safe_headers,
                "query": dict(request.query_params),
            },
            "matched_trigger_node_id": node_id,
        }
    }

    background_tasks.add_task(DeploymentService.run, workflow.id, trigger_context)

    return {"status": "accepted"}


@webhook_router.post("/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives push notifications from Google Cloud Pub/Sub."""
    _verify_pubsub_token(request)

    try:
        data = await request.json()

        encoded_data = data["message"]["data"]
        decoded_payload = base64.b64decode(encoded_data).decode("utf-8")
        notification = json.loads(decoded_payload)

        email_address = notification.get("emailAddress")
        new_history_id = notification.get("historyId")

        if not email_address or not new_history_id:
            return {"status": "ok", "message": "Notification ignored (missing keys)"}

        # ✨ todo: for a proper task queue implement celery or redis
        background_tasks.add_task(
            GmailService.handle_gmail_update, email_address, new_history_id
        )

        return {"status": "success", "message": "Processing started in background"}
    except Exception as e:
        logger.error(f"Failed to parse incoming Pub/Sub message: {e}")
        # Return 200 to ack bad payloads — Pub/Sub retrying a malformed message never fixes it.
        return {"status": "ok", "message": "Notification ignored (parse error)"}
