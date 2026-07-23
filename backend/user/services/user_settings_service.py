from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from user.models.user_settings import UserSettings
from user.schemas.user_settings import UserSettingsUpdate


class UserSettingsService:
    @staticmethod
    async def get_or_create(db: AsyncSession, user_id: UUID) -> UserSettings:
        """Return the user's settings row, creating a default one on first read."""
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            await db.commit()
            await db.refresh(settings)

        return settings

    @staticmethod
    async def update(
        db: AsyncSession, user_id: UUID, data: UserSettingsUpdate
    ) -> UserSettings:
        """Apply a partial update — only fields set on `data` are written."""
        settings = await UserSettingsService.get_or_create(db, user_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)

        await db.commit()
        await db.refresh(settings)
        return settings
