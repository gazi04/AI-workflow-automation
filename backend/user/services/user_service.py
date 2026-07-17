from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from user.models.user import User

import uuid


class UserService:
    # 🔴 todo: need to handle exceptions
    @staticmethod
    async def create(db: AsyncSession, email: str, hashed_password: str) -> User:
        new_user = User(id=uuid.uuid4(), email=email, password_hash=hashed_password)

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def get_or_create(db: AsyncSession, email: str) -> User:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return user

    @staticmethod
    async def get(db: AsyncSession, id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_email(db: AsyncSession, id: UUID) -> Optional[str]:
        result = await db.execute(select(User).where(User.id == id))
        user = result.scalar_one_or_none()
        return user.email if user else None
