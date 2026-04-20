"""Router: endpoints de registro, login y perfil de usuario."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from cloudrisk_api.database import usuarios as usuarios_repo
from cloudrisk_api.services.autenticacion import create_access_token, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: UserCreate):
    user = usuarios_repo.create_user(data.name, data.email, data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Email already registered")
    token = create_access_token(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = usuarios_repo.get_user_by_email(form.username)
    if not user or not usuarios_repo.verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["id"])
    safe_user = {k: v for k, v in user.items() if k != "hashed_password"}
    return {"access_token": token, "token_type": "bearer", "user": safe_user}


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    # Nunca exponemos el hash bcrypt al cliente, aunque la dependencia de
    # auth lo haya cargado desde el repo.
    return {k: v for k, v in current_user.items() if k != "hashed_password"}


@router.get("/leaderboard")
def leaderboard(limit: int = 10):
    return usuarios_repo.list_users_top(limit=limit)
