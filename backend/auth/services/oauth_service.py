from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from auth.models.oauth_state import OAuthState

_STATE_TTL_MINUTES = 10


class OAuthStateService:
    @staticmethod
    def create(db: Session, state: str) -> OAuthState:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MINUTES)
        record = OAuthState(state=state, expires_at=expires_at)
        db.add(record)
        db.commit()
        return record

    @staticmethod
    def consume(db: Session, state: str) -> bool:
        """Validate state exists and is not expired, then delete it. Returns False if invalid/expired."""
        record = db.query(OAuthState).filter_by(state=state).first()
        if not record or record.expires_at < datetime.now(timezone.utc):
            return False
        db.delete(record)
        db.commit()
        return True
