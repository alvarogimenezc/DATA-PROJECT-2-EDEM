"""Router: Battle initiation, resolution, and tactical advice."""

from __future__ import annotations

from datetime import datetime, timezone

import random
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from cloudrisk_api.configuracion import settings, MIN_GARRISON
from cloudrisk_api.database import batallas as batallas_repo, zonas as zonas_repo, clanes as clanes_repo, publicador_pubsub as pubsub_publisher
from cloudrisk_api.services.asesor_ia import get_battle_advice
from cloudrisk_api.services.autenticacion import get_current_user

# /battles/* está marcado deprecated: el sistema canónico de combate es
# POST /zones/{id}/attack (Risk dice). /battles/* se mantiene sólo para el
# historial y la resolución programada (Cloud Scheduler) y desaparecerá
# en la próxima major.
router = APIRouter(prefix="/battles", tags=["battles"], deprecated=True)


class BattleCreate(BaseModel):
    zone_id: str


@router.get("/")
def list_battles():
    return batallas_repo.list_ongoing_battles()


@router.get("/history")
def battle_history(limit: int = 10, current_user: dict = Depends(get_current_user)):
    clan_id = current_user.get("clan_id") or current_user.get("id")
    if not clan_id:
        return []
    battles = batallas_repo.list_battles_by_clan(clan_id, limit=limit)
    enriched = []
    for b in battles:
        zone = zonas_repo.get_zone_by_id(b.get("zone_id", ""))
        enriched.append({**b, "zone_name": zone.get("name", "Zona desconocida") if zone else "Zona desconocida"})
    return enriched


@router.get("/{battle_id}")
def get_battle(battle_id: str):
    battle = batallas_repo.get_battle_by_id(battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    return battle


@router.post("/", status_code=201)
async def initiate_battle(data: BattleCreate, request: Request, current_user: dict = Depends(get_current_user)):
    zone_id = data.zone_id
    if not current_user.get("clan_id"):
        raise HTTPException(status_code=400, detail="You must be in a clan to initiate battles")
    zone = zonas_repo.get_zone_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    if zone.get("owner_clan_id") == current_user["clan_id"]:
        raise HTTPException(status_code=400, detail="Cannot attack your own zone")
    if batallas_repo.get_ongoing_battle_in_zone(zone_id):
        raise HTTPException(status_code=400, detail="A battle is already ongoing in this zone")

    attacker_clan = clanes_repo.get_clan_by_id(current_user["clan_id"])
    defender_power = 0
    defender_clan_id = zone.get("owner_clan_id")
    if defender_clan_id:
        defender_clan = clanes_repo.get_clan_by_id(defender_clan_id)
        if defender_clan:
            defender_power = defender_clan.get("total_power", 0)

    battle = batallas_repo.create_battle(
        zone_id=zone_id,
        attacker_clan_id=current_user["clan_id"],
        defender_clan_id=defender_clan_id,
        attacker_power=attacker_clan.get("total_power", 0),
        defender_power=defender_power,
    )
    try:
        pubsub_publisher.publish_battle_event(battle, "battle_started")
    except Exception:
        pass

    # Notify defender clan members via WebSocket if manager is available
    try:
        manager = request.app.state.manager
        if defender_clan_id:
            await manager.broadcast_to_clan(defender_clan_id, {
                "event": "battle_started",
                "zone_id": zone_id,
                "zone_name": zone.get("name", ""),
                "text": f"⚔ ¡Tu zona '{zone.get('name', '')}' está siendo atacada!",
                "level": "error",
            })
    except AttributeError:
        pass  # manager not in app.state during tests

    return battle


@router.get("/{battle_id}/advice")
def battle_advice(battle_id: str, current_user: dict = Depends(get_current_user)):
    battle = batallas_repo.get_battle_by_id(battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    zone = zonas_repo.get_zone_by_id(battle["zone_id"])
    context = {
        "attacker_power": battle["attacker_power"],
        "defender_power": battle["defender_power"],
        "defense_level": zone.get("defense_level", 0) if zone else 0,
    }
    return {"battle_id": battle_id, "advice": get_battle_advice(context)}


@router.post("/{battle_id}/resolve")
def resolve_battle(
    battle_id: str,
    current_user: dict = Depends(get_current_user),
):
    battle = batallas_repo.get_battle_by_id(battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle["result"] != "ongoing":
        raise HTTPException(status_code=400, detail="Battle already resolved")

    # Only participants can resolve: attacker or defender.
    # Fall back to user id if no clan set (legacy 4-player lobby).
    user_clan = current_user.get("clan_id") or current_user.get("id")
    if user_clan not in (battle.get("attacker_clan_id"), battle.get("defender_clan_id")):
        raise HTTPException(status_code=403, detail="Forbidden: only participants can resolve")

    zone = zonas_repo.get_zone_by_id(battle["zone_id"])
    defense_bonus = zone.get("defense_level", 0) * 2 if zone else 0
    attacker_roll = random.randint(1, 6) + (battle["attacker_power"] // 10)
    defender_roll = random.randint(1, 6) + (battle["defender_power"] // 10) + defense_bonus

    if attacker_roll > defender_roll:
        result = "attacker_wins"
        batallas_repo.update_battle(battle_id, {"result": result})
        if zone:
            zonas_repo.update_zone(battle["zone_id"], {
                "owner_clan_id": battle["attacker_clan_id"],
                "conquered_at": datetime.utcnow().isoformat(),
                # Invariante del juego: toda zona propia mantiene >= MIN_GARRISON.
                "defense_level": MIN_GARRISON,
            })
    else:
        result = "defender_wins"
        batallas_repo.update_battle(battle_id, {"result": result})
        if zone:
            zonas_repo.update_zone(battle["zone_id"], {
                "defense_level": min(zone.get("defense_level", 0) + 1, 10),
            })

    return {
        "battle_id": battle_id,
        "result": result,
        "attacker_roll": attacker_roll,
        "defender_roll": defender_roll,
    }


@router.post("/resolve-expired", include_in_schema=False)
def resolve_expired_battles(x_scheduler_token: Optional[str] = Header(None, alias="X-Scheduler-Token")):
    """Auto-resolve all battles past their ends_at time. Called by Cloud Scheduler."""
    from cloudrisk_api.configuracion import settings
    if x_scheduler_token != settings.SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    now = datetime.now(timezone.utc)
    battles = batallas_repo.list_ongoing_battles()
    resolved = []

    for battle in battles:
        ends_at_str = battle.get("ends_at")
        if not ends_at_str:
            continue
        try:
            ends_at = datetime.fromisoformat(ends_at_str.replace("Z", "+00:00"))
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if ends_at > now:
            continue  # not expired yet

        zone = zonas_repo.get_zone_by_id(battle["zone_id"])
        defense_bonus = zone.get("defense_level", 0) * 2 if zone else 0
        attacker_roll = random.randint(1, 6) + (battle["attacker_power"] // 10)
        defender_roll = random.randint(1, 6) + (battle["defender_power"] // 10) + defense_bonus

        if attacker_roll > defender_roll:
            result = "attacker_wins"
            if zone:
                zonas_repo.update_zone(battle["zone_id"], {
                    "owner_clan_id": battle["attacker_clan_id"],
                    "conquered_at": datetime.utcnow().isoformat(),
                    "defense_level": 0,
                })
        else:
            result = "defender_wins"
            if zone:
                zonas_repo.update_zone(battle["zone_id"], {
                    "defense_level": min(zone.get("defense_level", 0) + 1, 10),
                })

        batallas_repo.update_battle(battle["id"], {"result": result})
        resolved.append({"battle_id": battle["id"], "result": result})

    return {"resolved": len(resolved), "battles": resolved}
