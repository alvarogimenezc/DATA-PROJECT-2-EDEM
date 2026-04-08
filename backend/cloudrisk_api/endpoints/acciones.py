"""
Endpoints de acciones del jugador: poner ejércitos en zonas.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cloudrisk_api.database import firestore_db, bigquery_db
from cloudrisk_api.database.firestore_db import GameError


router = APIRouter(
    prefix="/actions",
    tags=["actions"],
    responses={404: {"description": "Not found"}},
)


class PlaceAction(BaseModel):
    player_id: str = Field(..., examples=["player_001"])
    location_id: str = Field(..., examples=["ruzafa"])
    armies: int = Field(..., gt=0, examples=[5])


class PlaceResult(BaseModel):
    status: str
    action_id: str
    remaining_armies: int


@router.post("/place", response_model=PlaceResult, summary="Poner ejércitos en una zona")
def place_armies(action: PlaceAction):
    try:
        remaining = firestore_db.place_armies_transaction(
            player_id=action.player_id,
            location_id=action.location_id,
            armies=action.armies,
        )
    except GameError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    action_id = bigquery_db.insert_user_action(
        player_id=action.player_id,
        location_id=action.location_id,
        armies=action.armies,
    )
    return PlaceResult(status="ok", action_id=action_id, remaining_armies=remaining)
