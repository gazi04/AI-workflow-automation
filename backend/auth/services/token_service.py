from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional

from auth.models.refresh_token import RefreshToken
from auth.utils import create_access_token, create_refresh_token
from user.models.user import User


class TokenService:
    @staticmethod
    def refresh_token(db: Session, refresh_token: str) -> Optional[dict]:
        try:
            with db.begin():
                token_record = (
                    db.query(RefreshToken)
                    .join(User)
                    .filter(
                        RefreshToken.token == refresh_token,
                        RefreshToken.is_revoked == False, 
                        RefreshToken.expires_at > datetime.now(timezone.utc),
                        User.is_active,
                    )
                    .first()
                )

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
                    token=new_refresh_token_string,
                    expires_at=new_expires_at,
                )
                db.add(new_refresh_token_record)

                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token_string,
                }
        except Exception:
            db.rollback()
            raise
