import asyncio
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.models import RefreshToken, ConnectedAccount
from auth.scopes import GOOGLE_SCOPES, SLACK_SCOPES
from auth.services import (
    AccountService,
    TokenService,
    OAuthStateService,
    AuthCodeService,
)
from auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_refresh_token,
)
from core.config_loader import settings
from core.rate_limit import limiter
from core.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from core.crypto import encrypt_token
from core.database import get_db
from core.setup_logging import setup_logger
from gmail.services import GmailService
from user.models.user import User
from user.services.user_service import UserService

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
logger = setup_logger("Auth Router")


@auth_router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": f"Hello {user.email}"}


@auth_router.get("/exchange")
@limiter.limit("20/minute")
async def exchange_code(
    request: Request, code: str, db: AsyncSession = Depends(get_db)
):
    """Exchange a short-lived one-time code for auth cookies.

    Tokens are set as HttpOnly cookies (plus a readable CSRF cookie) instead of
    being returned in the body, so client-side JS never holds them.
    """
    access_token, refresh_token = await AuthCodeService.consume(db, code)
    if access_token is None or refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )

    payload = decode_access_token(access_token)
    response = JSONResponse(
        content={"user": {"id": payload.get("sub"), "email": payload.get("email")}}
    )
    set_auth_cookies(response, access_token, refresh_token, generate_csrf_token())
    return response


@auth_router.post("/refresh")
@limiter.limit("20/minute")
async def refresh_access_token(request: Request, db: AsyncSession = Depends(get_db)):
    """Rotate tokens using the refresh-token cookie; set the new tokens as cookies."""
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    new_tokens = await TokenService.refresh_token(db, refresh_token)
    if not new_tokens:
        logger.warning("Invalid refresh token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    payload = decode_access_token(new_tokens["access_token"])
    response = JSONResponse(
        content={"user": {"id": payload.get("sub"), "email": payload.get("email")}}
    )
    set_auth_cookies(
        response,
        new_tokens["access_token"],
        new_tokens["refresh_token"],
        generate_csrf_token(),
    )
    return response


@auth_router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Revoke the current refresh token and clear all auth cookies."""
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await TokenService.revoke(db, refresh_token)

    response = JSONResponse(content={"detail": "Logged out"})
    clear_auth_cookies(response)
    return response


@auth_router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the current user so the frontend can display it without a readable token."""
    return {"id": str(user.id), "email": user.email}


# ==================================================
# Configure OAuth flow
# ==================================================
# Google's public OAuth token endpoint, not a credential. Bound to a name here rather
# than inline so bandit's nosec applies to this line alone instead of the whole dict.
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"  # nosec B105

# Slack OAuth v2 endpoints (public, not credentials).
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"  # nosec B105


def get_google_flow(code_verifier: str | None = None):
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": GOOGLE_TOKEN_URI,
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
        code_verifier=code_verifier,
        # Each request builds a fresh Flow, so the auto-generated verifier from
        # the authorization step never survives to the callback step unless we
        # persist and restore it ourselves (see OAuthStateService).
        autogenerate_code_verifier=code_verifier is None,
    )


@auth_router.get("/connect/google")
async def connect_google(request: Request, db: AsyncSession = Depends(get_db)):
    flow = get_google_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    await OAuthStateService.create(db, state, code_verifier=flow.code_verifier)

    return {"auth_url": auth_url}


# must apply the same update (returning both access_token and refresh_token)
# 🔴 todo: need to refactor this bold endpoint IT'S TO BIGG
@auth_router.get("/callback/google")
async def callback_google(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    saved_account = None

    try:
        oauth_state = await OAuthStateService.consume(db, state)
        if not oauth_state:
            raise HTTPException(
                status_code=400, detail="Invalid or expired state parameter"
            )

        flow = get_google_flow(code_verifier=oauth_state.code_verifier)

        # google_auth_oauthlib and google.auth are synchronous: the token
        # exchange and the id_token verification (which fetches Google's signing
        # certs) both block the event loop for the whole process.
        await asyncio.to_thread(flow.fetch_token, code=code)
        credentials = flow.credentials

        try:
            user_info = await asyncio.to_thread(
                id_token.verify_oauth2_token,
                credentials.id_token,  # pyright: ignore[reportAttributeAccessIssue]
                requests.Request(),
                settings.google_oauth_client_id,
            )
            provider_account_id = user_info["sub"]
            provider_account_email = user_info["email"]
        except ValueError as e:
            logger.error(f"ValueError: Invalid ID token: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid ID token: {e}") from e

        user = await UserService.get_or_create(db, provider_account_email)

        existing_account = await AccountService.get_account_by_user_and_provider(
            db, user.id, "google"
        )

        if existing_account:
            existing_account.access_token = encrypt_token(credentials.token)
            existing_account.refresh_token = (
                encrypt_token(credentials.refresh_token)
                or existing_account.refresh_token
            )
            existing_account.token_expires_at = (
                datetime.fromtimestamp(credentials.expiry.timestamp(), tz=timezone.utc)
                if credentials.expiry
                else None
            )
            existing_account.scope = " ".join(credentials.scopes)
            existing_account.updated_at = datetime.now(timezone.utc)

            saved_account = existing_account
        else:
            connected_account = ConnectedAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=provider_account_id,
                access_token=encrypt_token(credentials.token),
                refresh_token=encrypt_token(credentials.refresh_token),
                token_expires_at=datetime.fromtimestamp(
                    credentials.expiry.timestamp(), tz=timezone.utc
                )
                if credentials.expiry
                else None,
                scope=" ".join(credentials.scopes),
                metadata_account={
                    "email": provider_account_email,
                    "name": user_info.get("name"),
                },
            )
            db.add(connected_account)

            saved_account = connected_account

        await db.commit()

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token_string, expires_at = create_refresh_token(user.id)

        new_refresh_token = RefreshToken(
            user_id=user.id,
            token=hash_refresh_token(refresh_token_string),
            expires_at=expires_at,
        )
        db.add(new_refresh_token)
        await db.commit()

        # After a successfull login with google enable gmail listener for push notifications
        watch_response = await GmailService.watch_mailbox_for_updates(
            user_id=user.id,
        )

        if watch_response and watch_response.get("historyId"):
            await AccountService.update_history_id(
                db, saved_account, watch_response["historyId"]
            )

        code = await AuthCodeService.create(db, access_token, refresh_token_string)
        frontend_url = f"{settings.frontend_url}/auth/success?code={code}"

        return RedirectResponse(url=frontend_url)

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=auth_failed")


# ==================================================
# Slack OAuth — a *connect* flow (the user is already authenticated), so unlike
# the Google callback it mints no app tokens, starts no Gmail watch, and never
# creates a user. Identity rides through the redirect on the OAuthState row.
# ==================================================
@auth_router.get("/connect/slack")
async def connect_slack(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if (
        settings.slack_oauth_client_id is None
        or settings.slack_oauth_redirect_uri is None
    ):
        raise HTTPException(
            status_code=503, detail="Slack integration is not configured."
        )

    state = secrets.token_urlsafe(32)
    await OAuthStateService.create(db, state, user_id=user.id, provider="slack")

    query = urlencode(
        {
            "client_id": settings.slack_oauth_client_id,
            "scope": ",".join(SLACK_SCOPES),
            "redirect_uri": settings.slack_oauth_redirect_uri,
            "state": state,
        }
    )
    return {"auth_url": f"{SLACK_AUTHORIZE_URL}?{query}"}


async def _exchange_slack_code(code: str) -> dict:
    """Trade an OAuth code for a Slack bot token via oauth.v2.access."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": settings.slack_oauth_client_id,
                "client_secret": settings.slack_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.slack_oauth_redirect_uri,
            },
            timeout=10,
        )
    return resp.json()


@auth_router.get("/callback/slack")
async def callback_slack(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    fail = RedirectResponse(
        url=f"{settings.frontend_url}/dashboard/integrations?error=slack_failed"
    )

    try:
        oauth_state = await OAuthStateService.consume(db, state)
        # Read identity off the row immediately — the record is deleted on
        # consume; matches how callback_google reads code_verifier.
        provider = oauth_state.provider if oauth_state else None
        owner_id = oauth_state.user_id if oauth_state else None
        if oauth_state is None or provider != "slack" or owner_id is None:
            logger.error("Slack callback: invalid/expired/mismatched state.")
            return fail

        data = await _exchange_slack_code(code)

        if not data.get("ok"):
            logger.error(f"Slack token exchange failed: {data.get('error')}")
            return fail

        team = data.get("team") or {}
        authed_user = data.get("authed_user") or {}
        # Slack returns scopes comma-delimited; the rest of the stack (drift
        # check, DB convention) is space-delimited.
        scope = " ".join(s for s in data.get("scope", "").split(",") if s)

        account = await AccountService.get_account_by_user_and_provider(
            db, owner_id, "slack"
        )
        if account is None:
            account = ConnectedAccount(
                user_id=owner_id,
                provider="slack",
                provider_account_id=team.get("id", ""),
            )
            db.add(account)

        account.access_token = encrypt_token(data["access_token"])
        account.refresh_token = None
        account.token_expires_at = None
        account.scope = scope
        account.provider_account_id = team.get("id", account.provider_account_id)
        account.is_connected = True
        account.metadata_account = {
            "team_id": team.get("id"),
            "team_name": team.get("name"),
            "bot_user_id": data.get("bot_user_id"),
            "authed_user_id": authed_user.get("id"),
        }
        account.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return RedirectResponse(url=f"{settings.frontend_url}/dashboard/integrations")

    except Exception as e:
        logger.error(f"Slack callback unhandled error: {e}")
        return fail
