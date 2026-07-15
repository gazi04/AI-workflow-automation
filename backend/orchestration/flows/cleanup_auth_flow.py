# The models are imported at the top level to resolve SQLAlchemy mapper
# string resolution and circular-import issues before any DB operation.
import core.models  # noqa: F401

from datetime import datetime, timezone

from prefect import flow, get_run_logger

from core.database import db_session
from core.setup_logging import setup_logger
from auth.models.oauth_state import OAuthState
from auth.models.auth_code import AuthCode
from auth.models.refresh_token import RefreshToken


@flow(name="Cleanup Expired Auth", log_prints=True)
def cleanup_expired_auth():
    """Delete expired auth rows so the tables don't grow without bound.

    `oauth_states` and `auth_codes` are deleted on use but linger when a flow is
    abandoned; `refresh_tokens` are only marked revoked/expired, never removed.
    Every row here carries `expires_at`, and each is dead once past it (a revoked
    refresh token is unusable regardless), so `expires_at < now` is a safe purge.
    Each table is swept independently — one failure must not abort the rest.
    """
    # Prefect's run logger surfaces output in the run logs; fall back to the local
    # logger when there is no Prefect run context (e.g. unit tests calling .fn).
    try:
        logger = get_run_logger()
    except Exception:
        logger = setup_logger("Cleanup Expired Auth")

    now = datetime.now(timezone.utc)

    with db_session() as db:
        for model in (OAuthState, AuthCode, RefreshToken):
            try:
                deleted = (
                    db.query(model)
                    .filter(model.expires_at < now)
                    .delete(synchronize_session=False)
                )
                db.commit()
                logger.info(f"Purged {deleted} expired {model.__tablename__} row(s)")
            except Exception as e:
                db.rollback()
                logger.error(f"Purge failed for {model.__tablename__}: {e}")
