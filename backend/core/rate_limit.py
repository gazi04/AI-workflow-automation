"""Shared slowapi Limiter.

Defined here (not in main.py) so routers can import it for their
`@limiter.limit(...)` decorators without a circular import back through
main.py, which itself imports the routers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config_loader import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)
