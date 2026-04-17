"""Auth service: JWT tokens + current user resolution via Firestore."""

from __future__ import annotations


from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from cloudrisk_api.configuracion import settings
from cloudrisk_api.database import usuarios as usuarios_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")
# Same endpoint URL, but this one does NOT error when the header is missing.
# Used by routes that accept BOTH an explicit body field AND auth fallback.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=False)


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise exc
    except JWTError:
        raise exc

    user = usuarios_repo.get_user_by_id(user_id)
    if not user:
        raise exc
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> Optional[dict]:
    """
    Like `get_current_user` but returns None instead of 401 when the client
    didn't send a token. Useful for endpoints that accept both an explicit
    body field (like team_compat `/actions/place` with player_id in body)
    AND auth (like our own frontend sending JWT without the body field).
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None
    return usuarios_repo.get_user_by_id(user_id)
