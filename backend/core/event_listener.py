"""Postgres LISTEN side of the workflow event pipeline.

Runs inside the FastAPI process. A daemon thread holds a dedicated autocommit
connection and ``LISTEN``s on the ``wf_events`` channel; each notification is
parsed and forwarded to the right user's WebSocket via the in-memory manager.
The worker process publishes the events (see ``core/events.py``).

psycopg2 is sync, so the listen loop lives in a thread and hands work back to the
API event loop with ``asyncio.run_coroutine_threadsafe``.
"""

import asyncio
import json
import select
import threading

import psycopg2
import psycopg2.extensions

from core.database import engine
from core.events import CHANNEL
from core.setup_logging import setup_logger
from core.websocket_manager import manager

logger = setup_logger("Event Listener")

_SELECT_TIMEOUT = 5  # seconds — bounds shutdown latency
_RECONNECT_BACKOFF = 2  # seconds


class EventListener:
    def __init__(self) -> None:
        self._loop = None
        self._thread = None
        self._stop = threading.Event()

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="wf-event-listener", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _dsn(self) -> str:
        # SQLAlchemy URL is ``postgresql+psycopg2://…``; psycopg2 wants plain libpq.
        return engine.url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            conn = None
            try:
                conn = psycopg2.connect(self._dsn())
                conn.set_isolation_level(
                    psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
                )
                with conn.cursor() as cur:
                    cur.execute(f"LISTEN {CHANNEL};")
                logger.info(f"Listening on Postgres channel '{CHANNEL}'")

                while not self._stop.is_set():
                    if select.select([conn], [], [], _SELECT_TIMEOUT) == ([], [], []):
                        continue
                    conn.poll()
                    while conn.notifies:
                        notify = conn.notifies.pop(0)
                        self._dispatch(notify.payload)
            except Exception as e:
                logger.error(f"Event listener connection error: {e}")
                self._stop.wait(_RECONNECT_BACKOFF)  # backoff before reconnect
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def _dispatch(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except Exception:
            logger.error(f"Discarding malformed event payload: {raw!r}")
            return

        user_id = payload.get("user_id")
        if not user_id or self._loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            manager.broadcast_to_user(user_id, payload), self._loop
        )


listener = EventListener()
