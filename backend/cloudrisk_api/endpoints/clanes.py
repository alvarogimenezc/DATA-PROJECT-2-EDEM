"""Router: Clan CRUD, join, and leave endpoints."""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from cloudrisk_api.database import clanes as clanes_repo, usuarios as usuarios_repo
from cloudrisk_api.services.autenticacion import get_current_user

router = APIRouter(prefix="/clans", tags=["clans"])


class ClanCreate(BaseModel):
    name: str
    color: Optional[str] = "#ff0000"


@router.post("/", status_code=201)
def create_clan(data: ClanCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("clan_id"):
        raise HTTPException(status_code=400, detail="Leave your current clan first")
    clan = clanes_repo.create_clan(data.name, data.color, created_by=current_user["id"])
    if not clan:
        raise HTTPException(status_code=400, detail="Clan name already taken")
    usuarios_repo.update_user(current_user["id"], {"clan_id": clan["id"]})
    clan["member_count"] = 1
    return clan


@router.get("/")
def list_clans():
    return clanes_repo.list_clans()


@router.post("/leave")
def leave_clan(current_user: dict = Depends(get_current_user)):
    if not current_user.get("clan_id"):
        raise HTTPException(status_code=400, detail="You are not in a clan")
    usuarios_repo.update_user(current_user["id"], {"clan_id": None})
    return {"message": "Left clan successfully"}


@router.post("/{clan_id}/delete")
def delete_clan(clan_id: str, current_user: dict = Depends(get_current_user)):
    clan = clanes_repo.get_clan_by_id(clan_id)
    if not clan:
        raise HTTPException(status_code=404, detail="Clan not found")
    # Allow deletion if: user is the creator, OR the crew has no members (orphaned crew)
    is_creator = clan.get("created_by") == current_user["id"]
    members = usuarios_repo.list_users_by_clan(clan_id)
    is_empty = len(members) == 0
    if not is_creator and not is_empty:
        raise HTTPException(status_code=403, detail="Solo el creador puede eliminar esta crew")
    for u in members:
        usuarios_repo.update_user(u["id"], {"clan_id": None})
    clanes_repo.delete_clan(clan_id)
    return {"message": "Clan deleted successfully"}


@router.post("/{clan_id}/join")
def join_clan(clan_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("clan_id"):
        raise HTTPException(status_code=400, detail="Leave your current clan first")
    clan = clanes_repo.get_clan_by_id(clan_id)
    if not clan:
        raise HTTPException(status_code=404, detail="Clan not found")
    usuarios_repo.update_user(current_user["id"], {"clan_id": clan_id})
    return {"message": f"Joined clan {clan['name']}"}
