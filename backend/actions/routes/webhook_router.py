from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from actions.services.gmail_service import GmailService
from auth.depedencies import get_current_user
from auth.services.account_service import AccountService
from core.database import get_db
from core.setup_logging import setup_logger
from user.models.user import User

import base64
import json


webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = setup_logger("Webhook router")


@webhook_router.get("/listen-to-gmail")
async def listen_gmail(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Initiate the webhook to get gmail push notifications"""
    try:
        google_account = await AccountService.get_account(db, user.id, "google")
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

    watch_response = await GmailService.watch_mailbox_for_updates(user_id=user.id)

    if watch_response and watch_response.get("historyId"):
        await AccountService.update_history_id(
            db, google_account, watch_response["historyId"]
        )


@webhook_router.post("/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives push notifications from Google Cloud Pub/Sub."""
    try:
        data = await request.json()

        encoded_data = data["message"]["data"]
        decoded_payload = base64.b64decode(encoded_data).decode("utf-8")
        notification = json.loads(decoded_payload)

        email_address = notification.get("emailAddress")
        new_history_id = notification.get("historyId")

        if not email_address or not new_history_id:
            # Still return 200/204 to avoid retries for bad payload format
            return {"status": "ok", "message": "Notification ignored (missing keys)"}

        # ✨ todo: for a proper task queue implement celery or redis
        background_tasks.add_task(
            GmailService.handle_gmail_update, email_address, new_history_id
        )

        return {"status": "success", "message": "Processing started in background"}
    except Exception as e:
        logger.error(f"Failed to parse incoming Pub/Sub message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process notification. This is the error: \n{e}",
        )
