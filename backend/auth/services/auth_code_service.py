import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.auth_code import AuthCode

_CODE_TTL_SECONDS = 60


class AuthCodeService:
    @staticmethod
    async def create(db: AsyncSession, access_token: str, refresh_token: str) -> str:
        code = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CODE_TTL_SECONDS)
        db.add(AuthCode(code=code, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at))
        await db.commit()
        return code

    @staticmethod
    async def consume(db: AsyncSession, code: str) -> tuple[str, str] | tuple[None, None]:
        result = await db.execute(select(AuthCode).filter_by(code=code))
        record = result.scalar_one_or_none()
        if not record or record.expires_at < datetime.now(timezone.utc):
            return None, None
        access_token, refresh_token = record.access_token, record.refresh_token
        await db.delete(record)
        await db.commit()
        return access_token, refresh_token
