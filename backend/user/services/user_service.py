from sqlalchemy.orm import Session
from uuid import UUID

from user.models.user import User

import uuid


class UserService:
    # 🔴 todo: need to handle exceptions
    @staticmethod
    def create_user(db: Session, email: str, hashed_password: str) -> User:
        new_user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hashed_password
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def get_or_create_user(db: Session, email: str) -> User:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, id: UUID) -> User:
        return db.query(User).filter(User.id == id).first()
