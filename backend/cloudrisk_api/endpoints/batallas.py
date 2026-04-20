"""Router: Battle history + legacy resolve (manual + Scheduler cron).

Nota: el sistema canónico de combate es `POST /zones/{id}/attack` (Risk dice).
Este router mantiene sólo lo que sigue activo en producción:
- `GET /battles/`, `GET /battles/history`, `POST /battles/{id}/resolve` (consumidos por el frontend)
- `POST /battles/resolve-expired` (Cloud Scheduler cron)
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from cloudrisk_api.configuracion import settings, MIN_GARRISON
from cloudrisk_api.database import batallas as batallas_repo, zonas as zonas_repo
from cloudrisk_api.services.autenticacion import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/battles", tags=["battles"], deprecated=True)


def _compute_battle_roll(power: int, defense_bonus: int = 0) -> int:
    """Tirada del sistema legacy: `d6 + (power // 10) + defense_bonus`.

    Se comparte entre `POST /{id}/resolve` y `POST /resolve-expired` (cron).
    """
    return random.randint(1, 6) + (power // 10) + defense_bonus


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

    # Fall back to user id if no clan set (legacy 4-player lobby).
    user_clan = current_user.get("clan_id") or current_user.get("id")
    if user_clan not in (battle.get("attacker_clan_id"), battle.get("defender_clan_id")):
        raise HTTPException(status_code=403, detail="Forbidden: only participants can resolve")

    zone = zonas_repo.get_zone_by_id(battle["zone_id"])
    defense_bonus = zone.get("defense_level", 0) * 2 if zone else 0
    attacker_roll = _compute_battle_roll(battle["attacker_power"])
    defender_roll = _compute_battle_roll(battle["defender_power"], defense_bonus)

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
    """Auto-resuelve batallas vencidas. Llamado por Cloud Scheduler."""
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
            continue

        zone = zonas_repo.get_zone_by_id(battle["zone_id"])
        defense_bonus = zone.get("defense_level", 0) * 2 if zone else 0
        attacker_roll = _compute_battle_roll(battle["attacker_power"])
        defender_roll = _compute_battle_roll(battle["defender_power"], defense_bonus)

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
