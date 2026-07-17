from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.models.refresh_token import RefreshToken
from auth.utils import create_access_token, create_refresh_token, hash_refresh_token
from user.models.user import User


class TokenService:
    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> Optional[dict]:
        try:
            async with db.begin():
                result = await db.execute(
                    select(RefreshToken)
                    .join(User)
                    .options(selectinload(RefreshToken.user))
                    .where(
                        RefreshToken.token == hash_refresh_token(refresh_token),
                        RefreshToken.is_revoked == False,  # noqa: E712
                        RefreshToken.expires_at > datetime.now(timezone.utc),
                        User.is_active,
                    )
                )
                token_record = result.scalar_one_or_none()

                if not token_record:
                    return None

                token_record.is_revoked = True

                new_access_token = create_access_token(
                    data={
                        "sub": str(token_record.user_id),
                        "email": token_record.user.email,
                    }
                )
                new_refresh_token_string, new_expires_at = create_refresh_token(
                    token_record.user_id
                )

                new_refresh_token_record = RefreshToken(
                    user_id=token_record.user_id,
                    token=hash_refresh_token(new_refresh_token_string),
                    expires_at=new_expires_at,
                )
                db.add(new_refresh_token_record)

                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token_string,
                }
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def revoke(db: AsyncSession, refresh_token: str) -> None:
        """Mark a refresh token revoked (used on logout). No-op if not found."""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token == hash_refresh_token(refresh_token)
            )
        )
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.is_revoked = True
            await db.commit()
