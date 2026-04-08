"""
Endpoints de lectura del estado del juego: balance del jugador y zonas del mapa.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from cloudrisk_api.database import firestore_db


router = APIRouter(
    prefix="/state",
    tags=["state"],
    responses={404: {"description": "Not found"}},
)


class UserState(BaseModel):
    player_id: str
    armies: int = 0
    total_steps: int = 0
    updated_at: str | None = None


class Location(BaseModel):
    location_id: str
    armies: int = 0
    owner: str | None = None
    updated_at: str | None = None


@router.get("/player/{player_id}", response_model=UserState, summary="Estado de un jugador")
def get_player_state(player_id: str):
    data = firestore_db.get_user_balance(player_id)
    return UserState(
        player_id=player_id,
        armies=int(data.get("armies", 0)),
        total_steps=int(data.get("total_steps", 0)),
        updated_at=str(data.get("updated_at")) if data.get("updated_at") else None,
    )


@router.get("/locations", response_model=list[Location], summary="Lista de zonas del mapa")
def get_locations():
    locs = firestore_db.list_locations()
    return [
        Location(
            location_id=l["location_id"],
            armies=int(l.get("armies", 0)),
            owner=l.get("owner"),
            updated_at=str(l.get("updated_at")) if l.get("updated_at") else None,
        )
        for l in locs
    ]
