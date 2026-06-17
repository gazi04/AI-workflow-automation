import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from auth.models.auth_code import AuthCode

_CODE_TTL_SECONDS = 60


class AuthCodeService:
    @staticmethod
    def create(db: Session, access_token: str, refresh_token: str) -> str:
        code = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CODE_TTL_SECONDS)
        db.add(AuthCode(code=code, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at))
        db.commit()
        return code

    @staticmethod
    def consume(db: Session, code: str) -> tuple[str, str] | tuple[None, None]:
        record = db.query(AuthCode).filter_by(code=code).first()
        if not record or record.expires_at < datetime.now(timezone.utc):
            return None, None
        access_token, refresh_token = record.access_token, record.refresh_token
        db.delete(record)
        db.commit()
        return access_token, refresh_token
