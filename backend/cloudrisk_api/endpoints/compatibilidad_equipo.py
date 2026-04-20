"""
CloudRISK — Team Contract Alias Routes
Thin wrappers that expose the team repo's 3-endpoint API contract on top
of our richer routers. Match alvarogimenezc/DATA-PROJECT-2-EDEM exactly:

    GET  /api/v1/state/player/{player_id}   → {armies, total_steps, updated_at}
    GET  /api/v1/state/locations            → [{location_id, armies, owner, ...}]
    POST /api/v1/actions/place              → body {player_id, location_id, armies}

Unauthenticated by contract (see their cloudrisk_api/endpoints/estado.py).

EDEM. Master Big Data & Cloud 2025/2026
Professor: Javi Briones & Adriana Campos
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cloudrisk_api.configuracion import MAX_ZONE_DEFENSE
from cloudrisk_api.database import usuarios as usuarios_repo, zonas as zonas_repo
from cloudrisk_api.services.autenticacion import get_current_user_optional


router = APIRouter(tags=["team-contract"])


# ─── Response models match the team's Pydantic classes ────────────────

class UserState(BaseModel):
    player_id: str
    armies: int = 0
    total_steps: int = 0
    updated_at: str | None = None


class Location(BaseModel):
    # ─── Contract minimum (respects alvarogimenezc/DATA-PROJECT-2-EDEM) ───
    location_id: str
    armies: int = 0
    owner: str | None = None
    updated_at: str | None = None
    # ─── Frontend extensions (optional — strict contract consumers ignore) ─
    id: str | None = None                  # alias of location_id
    name: str | None = None                # human-readable zone name
    total_armies: int | None = None        # alias of armies for UI
    owner_clan_id: str | None = None
    owner_clan_name: str | None = None
    owner_clan_color: str | None = None
    garrisons: dict | None = None
    value_score: float | None = None


class PlaceAction(BaseModel):
    # `player_id` is required by the contract, but we accept it missing and
    # infer from the auth token when called internally by the frontend
    # (which doesn't ship a player_id body field — the JWT already has it).
    player_id: str | None = Field(None, examples=["demo-player-001"])
    location_id: str = Field(..., examples=["zona-russafa"])
    # Contract uses 'armies'; the legacy /armies/place used 'amount'. Accept
    # either for backward compatibility.
    armies: int | None = Field(None, gt=0, examples=[5])
    amount: int | None = Field(None, gt=0, examples=[5])

    def resolved_armies(self) -> int:
        """Return whichever of `armies` or `amount` the caller supplied."""
        return self.armies if self.armies is not None else (self.amount or 0)


class PlaceResult(BaseModel):
    status: str
    action_id: str
    remaining_armies: int


# ─── /state/{player_id} ───────────────────────────────────────────────

@router.get("/state/player/{player_id}", response_model=UserState,
            summary="Team contract: a player's balance")
def get_player_state(player_id: str):
    """Return the player's armies + step count. Adapts our richer user doc."""
    user = usuarios_repo.get_user_by_id(player_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")
    return UserState(
        player_id=player_id,
        armies=int(user.get("power_points") or 0),     # our "power" = team's "armies"
        total_steps=int(user.get("steps_total") or 0),
        updated_at=_iso_now(),
    )


# ─── /state/locations ─────────────────────────────────────────────────

@router.get("/state/locations", response_model=list[Location],
            summary="Team contract: all zones with armies + owner")
def list_locations():
    """
    Return all zones as Location objects. The response carries the contract
    fields (location_id, armies, owner, updated_at) plus richer optional
    fields our frontend consumes (name, garrisons, value_score). Strict
    contract consumers ignore the extras.
    """
    out: list[Location] = []
    now = _iso_now()
    for z in zonas_repo.list_zones():
        defense = int(z.get("defense_level") or 0)
        owner = z.get("owner_clan_id") or None
        out.append(Location(
            # contract minimum
            location_id=z["id"],
            armies=defense,
            owner=owner,
            updated_at=now,
            # frontend extensions
            id=z["id"],
            name=z.get("name"),
            total_armies=defense,
            owner_clan_id=owner,
            owner_clan_name="",
            owner_clan_color="",
            garrisons={},
            value_score=float(z.get("value", 0) or 0),
        ))
    return out


# ─── /actions/place ──────────────────────────────────────────────────

@router.post("/actions/place", response_model=PlaceResult,
             summary="Team contract: deploy armies to a zone")
def place_armies(
    action: PlaceAction,
    current_user: dict | None = Depends(get_current_user_optional),
):
    # Resolve `player_id`:
    #   1. use explicit body field if the caller sent it (contract compliance),
    #   2. otherwise fall back to the authenticated user (frontend case).
    player_id = action.player_id or (current_user["id"] if current_user else None)
    if not player_id:
        raise HTTPException(
            status_code=400,
            detail="player_id required (either in body or via Authorization header)",
        )

    # Resolve armies: contract uses 'armies', legacy /armies/place uses 'amount'.
    armies_to_place = action.resolved_armies()
    if armies_to_place <= 0:
        raise HTTPException(
            status_code=400,
            detail="armies (or amount) must be > 0",
        )

    user = usuarios_repo.get_user_by_id(player_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")
    zone = zonas_repo.get_zone_by_id(action.location_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"location {action.location_id} not found")

    current = int(user.get("power_points") or 0)
    if current < armies_to_place:
        raise HTTPException(
            status_code=400,
            detail=f"insufficient armies: have {current}, need {armies_to_place}",
        )

    # Apply environmental multipliers so deployments through this contract
    # behave like our own /armies/place — same house rules for everyone.
    from cloudrisk_api.services import multiplicadores as multipliers
    snap = multipliers.current()
    effective = max(1, round(armies_to_place * snap.combined))

    new_defense = min(int(zone.get("defense_level") or 0) + effective, MAX_ZONE_DEFENSE)
    zonas_repo.update_zone(action.location_id, {
        "defense_level": new_defense,
        "owner_clan_id": player_id,
    })
    new_power = max(0, current - armies_to_place)
    usuarios_repo.update_user(player_id, {"power_points": new_power})

    return PlaceResult(
        status="ok",
        action_id=f"act-{int(datetime.now(tz=timezone.utc).timestamp() * 1000)}",
        remaining_armies=new_power,
    )


# ─── helpers ─────────────────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
