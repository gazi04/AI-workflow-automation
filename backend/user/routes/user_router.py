from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from core.database import get_db
from user.models import User
from user.schemas.user_settings import UserSettingsRead, UserSettingsUpdate
from user.services.user_settings_service import UserSettingsService

user_router = APIRouter(prefix="/user", tags=["User"])


@user_router.get("/settings", response_model=UserSettingsRead)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the current user's settings, creating defaults on first access."""
    return await UserSettingsService.get_or_create(db, user.id)


@user_router.patch("/settings", response_model=UserSettingsRead)
async def update_settings(
    data: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Partially update the current user's settings."""
    return await UserSettingsService.update(db, user.id, data)
