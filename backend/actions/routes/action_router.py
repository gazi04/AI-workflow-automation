from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from actions.services.gmail_service import GmailService
from auth.depedencies import get_current_user
from core.database import get_db
from user.models.user import User


action_router = APIRouter(
    prefix="/action",
    tags=["Action"]
)

@action_router.get("/create_draft")
async def create_draft_with_gmail(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await GmailService.create_draft(db, user.id)

@action_router.get("/send_email")
async def send_mail_in_gmail(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await GmailService.send_message(db, user.id)
