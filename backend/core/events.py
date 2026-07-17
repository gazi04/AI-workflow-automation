"""Cross-process event publishing via Postgres LISTEN/NOTIFY.

The Prefect worker runs in a separate process from the FastAPI app that owns the
in-memory WebSocket manager, so it cannot push to sockets directly. Instead it
emits events on the ``wf_events`` Postgres channel; the API process listens (see
``core/event_listener.py``) and forwards them to the right user's WebSocket.
"""

import json

from sqlalchemy import text

from core.database import db_session
from core.setup_logging import setup_logger

logger = setup_logger("Event Publisher")

# Postgres NOTIFY payloads are capped at 8000 bytes; keep error strings short so
# the whole JSON document stays comfortably under the limit.
CHANNEL = "wf_events"
_MAX_ERROR_LEN = 500


async def publish_event(payload: dict) -> None:
    """Emit a workflow event on the ``wf_events`` channel.

    Best-effort: a publish failure is logged but never propagated, so a broken
    notification can't fail a workflow run.
    """
    try:
        if payload.get("error"):
            payload = {**payload, "error": str(payload["error"])[:_MAX_ERROR_LEN]}

        message = json.dumps(payload)
        # pg_notify only delivers on COMMIT, so commit immediately.
        async with db_session() as db:
            await db.execute(text("SELECT pg_notify(:channel, :payload)"),
                              {"channel": CHANNEL, "payload": message})
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to publish workflow event {payload.get('type')}: {e}")
