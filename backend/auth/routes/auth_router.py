from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.orm import Session

from auth.depedencies import get_current_user
from auth.models import RefreshToken
from auth.models import ConnectedAccount
from auth.schemas import UserLogin, Token, RefreshTokenRequest
from auth.services.auth_service import AuthService
from auth.services.token_service import TokenService
from auth.utils import create_access_token, create_refresh_token, verify_password
from core.config_loader import settings
from core.database import get_db
from user.models.user import User
from user.services.user_service import UserService

auth_router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@auth_router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": f"Hello {user.email}"}

# 🔴 todo: need add validation to email and password
@auth_router.post("/register", status_code=201)
async def register_user(user_data: UserLogin, db: Session = Depends(get_db)):
    existing_user = UserService.get_user_by_email(db, user_data.email)

    if existing_user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    AuthService.register_user(db, user_data)

    return {"message": "User registered successfully"}


@auth_router.post("/token", response_model=Token)
# 🔴 todo: missing input validation & rate limiting
# doens't provice protection against brute force attacks, too many registration attemps and invalid inputs
async def login_for_access_token(user_data: UserLogin, db: Session = Depends(get_db)):
    user = UserService.get_user_by_email(db, user_data.email)

    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    tokens = AuthService.create_token_pair(db, user)

    return {**tokens, "token_type": "bearer"}

@auth_router.post("/refresh", response_model=Token)
async def refresh_access_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    new_tokens = TokenService.refresh_token(db, request.refresh_token)
    if not new_tokens:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    return {**new_tokens, "token_type": "bearer"}

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
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",  # This scope is to get the user's ID
        ],
        redirect_uri = settings.google_oauth_redirect_uri,
    )




# 🔴 todo: this dictionary can cause memory leakage
# suggestion: use database
user_sessions = {}


@auth_router.get("/connect/google")
async def connect_google(request: Request):
    flow = get_google_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    user_sessions[state] = {"state": state}

    return {"auth_url": auth_url}

# must apply the same update (returning both access_token and refresh_token)
@auth_router.get("/callback/google")
async def callback_google(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    try:
        if state not in user_sessions:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

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
            raise HTTPException(status_code=400, detail=f"Invalid ID token: {e}")

        user = UserService.get_or_create_user(db, provider_account_email)

        existing_account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.provider == "google",
                ConnectedAccount.provider_account_id == provider_account_id,
            )
            .first()
        )

        if existing_account:
            existing_account.access_token = credentials.token
            existing_account.refresh_token = (
                credentials.refresh_token or existing_account.refresh_token
            )
            existing_account.token_expires_at = (
                datetime.fromtimestamp(credentials.expiry.timestamp(), tz=timezone.utc)
                if credentials.expiry
                else None
            )
            existing_account.scope = credentials.scopes
            existing_account.updated_at = datetime.now(timezone.utc)
        else:
            connected_account = ConnectedAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=provider_account_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=datetime.fromtimestamp(credentials.expiry.timestamp(), tz=timezone.utc)
                if credentials.expiry
                else None,
                scope=credentials.scopes,
                metadata_account={
                    "email": provider_account_email,
                    "name": user_info.get("name"),
                },
            )
            db.add(connected_account)

        db.commit() 

        access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
        refresh_token_string, expires_at = create_refresh_token(user.id)

        new_refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_string,
            expires_at=expires_at
        )
        db.add(new_refresh_token)
        db.commit()
        
        if state in user_sessions:
            del user_sessions[state]

        return JSONResponse(content={
            "access_token": access_token,
            "refresh_token": refresh_token_string,
            "token_type": "bearer",
            "message": "User successfully logged in with Google"
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
