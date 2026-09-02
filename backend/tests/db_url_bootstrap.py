"""Point the test suite at a reachable Postgres.

`backend/.env` sets DATABASE_URL to the Docker-internal host `postgres`. Outside
`docker compose up` that name doesn't resolve and the whole suite dies on a DNS
error with no hint why. Honor an explicit TEST_DATABASE_URL, else rewrite an
unresolvable host to localhost.

Importing this module has the side effect of mutating `settings.database_url`,
so `tests/conftest.py` imports it *before* `core.models` — that pulls in
`core.database`, which builds its module-level engine from the setting at import
time, and mutating it afterwards has no effect.
"""

import os
import socket

from sqlalchemy.engine.url import make_url

from core.config_loader import settings


def _resolves(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


_override = os.environ.get("TEST_DATABASE_URL")
if _override:
    settings.database_url = _override
else:
    _url = make_url(settings.database_url)
    if _url.host and not _resolves(_url.host):
        settings.database_url = str(_url.set(host="localhost"))
