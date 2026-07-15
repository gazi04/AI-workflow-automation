from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.models import RefreshToken, ConnectedAccount
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
def exchange_code(request: Request, code: str, db: Session = Depends(get_db)):
    """Exchange a short-lived one-time code for auth cookies.

    Tokens are set as HttpOnly cookies (plus a readable CSRF cookie) instead of
    being returned in the body, so client-side JS never holds them.
    """
    access_token, refresh_token = AuthCodeService.consume(db, code)
    if access_token is None:
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
async def refresh_access_token(request: Request, db: Session = Depends(get_db)):
    """Rotate tokens using the refresh-token cookie; set the new tokens as cookies."""
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    new_tokens = TokenService.refresh_token(db, refresh_token)
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
async def logout(request: Request, db: Session = Depends(get_db)):
    """Revoke the current refresh token and clear all auth cookies."""
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        TokenService.revoke(db, refresh_token)

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
def get_google_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",  # This scope is to get the user's ID
        ],
        redirect_uri=settings.google_oauth_redirect_uri,
    )


@auth_router.get("/connect/google")
async def connect_google(request: Request, db: Session = Depends(get_db)):
    flow = get_google_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    OAuthStateService.create(db, state)

    return {"auth_url": auth_url}


# must apply the same update (returning both access_token and refresh_token)
# 🔴 todo: need to refactor this bold endpoint IT'S TO BIGG
@auth_router.get("/callback/google")
async def callback_google(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    saved_account = None

    try:
        if not OAuthStateService.consume(db, state):
            raise HTTPException(
                status_code=400, detail="Invalid or expired state parameter"
            )

        flow = get_google_flow()

        flow.fetch_token(code=code)
        credentials = flow.credentials

        try:
            user_info = id_token.verify_oauth2_token(
                credentials.id_token,
                requests.Request(),
                settings.google_oauth_client_id,
            )
            provider_account_id = user_info["sub"]
            provider_account_email = user_info["email"]
        except ValueError as e:
            logger.error(f"ValueError: Invalid ID token: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid ID token: {e}")

        user = UserService.get_or_create(db, provider_account_email)

        existing_account = AccountService.get_account_by_user_and_provider(
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
            existing_account.scope = credentials.scopes
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
                scope=credentials.scopes,
                metadata_account={
                    "email": provider_account_email,
                    "name": user_info.get("name"),
                },
            )
            db.add(connected_account)

            saved_account = connected_account

        db.commit()

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
        db.commit()

        # After a successfull login with google enable gmail listener for push notifications
        watch_response = GmailService.watch_mailbox_for_updates(
            user_id=user.id,
        )

        if watch_response and watch_response.get("historyId"):
            AccountService.update_history_id(
                db, saved_account, watch_response["historyId"]
            )

        code = AuthCodeService.create(db, access_token, refresh_token_string)
        frontend_url = f"{settings.frontend_url}/auth/success?code={code}"

        return RedirectResponse(url=frontend_url)

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=auth_failed")
