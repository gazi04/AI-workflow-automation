from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User, ConnectedAccount
import os
from datetime import datetime
import uuid

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests

from utils.security import create_access_token, get_password_hash, verify_password
from schemas import Token, UserLogin

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Configure a JWT token dependency to protect routes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


@router.post("/register", status_code=201)
async def register_user(user_data: UserLogin, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)

    new_user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        password_hash=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}


@router.post("/token", response_model=Token)
async def login_for_access_token(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# Configure OAuth flow
def get_google_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",  # This scope is to get the user's ID
        ],
        redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI"),
    )


async def get_or_create_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            id=uuid.uuid4(),
            email=email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


user_sessions = {}


@router.get("/connect/google")
async def connect_google(request: Request):
    flow = get_google_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    user_sessions[state] = {"state": state}

    return {"auth_url": auth_url}


@router.get("/callback/google")
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
                os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            )
            provider_account_id = user_info["sub"]
            provider_account_email = user_info["email"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid ID token: {e}")

        user = await get_or_create_user(db, provider_account_email)

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
                datetime.utcfromtimestamp(credentials.expiry.timestamp())
                if credentials.expiry
                else None
            )
            existing_account.scope = credentials.scopes
            existing_account.updated_at = datetime.utcnow()
        else:
            connected_account = ConnectedAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=provider_account_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=datetime.utcfromtimestamp(
                    credentials.expiry.timestamp()
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

        db.commit()

        if state in user_sessions:
            del user_sessions[state]

        return RedirectResponse(url="http://localhost:5173/connections?status=success")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
