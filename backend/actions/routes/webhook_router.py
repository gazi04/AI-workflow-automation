from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.depedencies import get_current_user
from actions.services.gmail_service import GmailService
from auth.services.account_service import AccountService
from core.database import get_db
from user.models.user import User

import base64
import json
import logging


webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@webhook_router.get("/listen-to-gmail")
async def listen_gmail(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Initiate the webhook to get gmail push notifications"""
    try:
        google_account = await AccountService.get_account(db, user.id, "google")
        if not google_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Google account connection not found for user."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve connected account: {e}"
        )

    watch_response = await GmailService.watch_mailbox_for_updates(
        db=db, 
        user_id=user.id, 
    )

    if watch_response and watch_response.get('historyId'):
         await AccountService.update_history_id(db, google_account, watch_response["historyId"])


@webhook_router.post("/gmail")
async def gmail_webhook(
    request: Request, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """Receives push notifications from Google Cloud Pub/Sub."""
    try:
        data = await request.json()
        
        # 1. Decode the Pub/Sub wrapper
        encoded_data = data['message']['data']
        decoded_payload = base64.b64decode(encoded_data).decode('utf-8')
        notification = json.loads(decoded_payload)
        
        email_address = notification.get('emailAddress')
        new_history_id = notification.get('historyId')

        if not email_address or not new_history_id:
            # Still return 200/204 to avoid retries for bad payload format
            return {"status": "ok", "message": "Notification ignored (missing keys)"}

        # 2. Add the processing logic to the background
        background_tasks.add_task(
            GmailService.handle_gmail_update, 
            db,
            email_address, 
            new_history_id
        )

        # 3. CRITICAL: Return a 200 OK immediately
        # This prevents Pub/Sub from retrying the message.
        return {"status": "success", "message": "Processing started in background"}
    except Exception as e:
        # Log the error but still return a 2xx status for production systems 
        # to avoid retry storms, or return 500 if you want Pub/Sub to retry.
        logging.error(f"Failed to parse incoming Pub/Sub message: {e}")
        # Returning 500 will make Pub/Sub retry the message
        raise HTTPException(status_code=500, detail="Failed to process notification")

