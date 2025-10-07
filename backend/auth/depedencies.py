import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from user.services.user_service import UserService
from utils.security import decode_access_token
from core.database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Dependency function to retrieve and validate the current authenticated user 
    based on the access token provided in the Authorization header.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise credentials_exception

    except PyJWTError:
        raise credentials_exception

    user = UserService.get_user_by_id(db, user_id)
    
    if user is None:
        raise credentials_exception

    return user
