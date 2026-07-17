from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.oauth_state import OAuthState

_STATE_TTL_MINUTES = 10


class OAuthStateService:
    @staticmethod
    async def create(db: AsyncSession, state: str) -> OAuthState:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MINUTES)
        record = OAuthState(state=state, expires_at=expires_at)
        db.add(record)
        await db.commit()
        return record

    @staticmethod
    async def consume(db: AsyncSession, state: str) -> bool:
        """Validate state exists and is not expired, then delete it. Returns False if invalid/expired."""
        result = await db.execute(select(OAuthState).filter_by(state=state))
        record = result.scalar_one_or_none()
        if not record or record.expires_at < datetime.now(timezone.utc):
            return False
        await db.delete(record)
        await db.commit()
        return True
