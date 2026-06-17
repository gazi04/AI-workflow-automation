"""Auth cookie helpers.

Tokens are delivered to the browser as cookies so client-side JS never touches
them: `access_token` / `refresh_token` are HttpOnly; `csrf_token` is readable so
the frontend can mirror it into an `X-CSRF-Token` header (double-submit CSRF).
Cookie attributes come from settings so prod can flip Secure/SameSite=None.
"""

import secrets

from fastapi import Response

from core.config_loader import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"

_ACCESS_MAX_AGE = settings.access_token_expire_minutes * 60
_REFRESH_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set(
    response: Response, key: str, value: str, max_age: int, httponly: bool
) -> None:
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=httponly,
        samesite=settings.cookie_samesite,
    )


def set_auth_cookies(
    response: Response, access_token: str, refresh_token: str, csrf_token: str
) -> None:
    _set(response, ACCESS_COOKIE, access_token, _ACCESS_MAX_AGE, httponly=True)
    _set(response, REFRESH_COOKIE, refresh_token, _REFRESH_MAX_AGE, httponly=True)
    # CSRF token must be readable by JS to mirror into the request header.
    _set(response, CSRF_COOKIE, csrf_token, _REFRESH_MAX_AGE, httponly=False)


def clear_auth_cookies(response: Response) -> None:
    for key in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(key=key, path="/", domain=settings.cookie_domain)
