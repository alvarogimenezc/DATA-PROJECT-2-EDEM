"""Router: Daily missions — compute completion from live data, reward on claim."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from cloudrisk_api.database import (
    usuarios as repository_users,
    batallas as repository_battles,
    zonas as repository_zones,
    pasos as repository_steps,
)
from cloudrisk_api.services.autenticacion import get_current_user

router = APIRouter(prefix="/missions", tags=["missions"])

USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"
COLLECTION = "mission_claims"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=os.environ.get("PROJECT_ID", "cloudrisk-local"))


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Mission catalogue ──────────────────────────────────────────────────────
MISSION_CATALOGUE = [
    {
        "id": "daily_steps_1k",
        "title": "Primer Kilómetro",
        "description": "Sincroniza 1.000 pasos hoy",
        "icon": "Footprints",
        "color": "#caff33",
        "reward_power": 10,
        "reward_gold": 20,
        "target": 1000,
        "type": "steps_today",
    },
    {
        "id": "daily_steps_5k",
        "title": "Velocista Urbano",
        "description": "Sincroniza 5.000 pasos hoy",
        "icon": "Zap",
        "color": "#ff8c2a",
        "reward_power": 50,
        "reward_gold": 100,
        "target": 5000,
        "type": "steps_today",
    },
    {
        "id": "conquer_zone",
        "title": "Conquistador",
        "description": "Ten al menos 1 zona bajo control de tu clan",
        "icon": "Crown",
        "color": "#ff2d92",
        "reward_power": 15,
        "reward_gold": 30,
        "target": 1,
        "type": "zones_owned",
    },
    {
        "id": "conquer_3zones",
        "title": "Dominador",
        "description": "Ten al menos 3 zonas bajo control de tu clan",
        "icon": "MapIcon",
        "color": "#9a4dff",
        "reward_power": 30,
        "reward_gold": 80,
        "target": 3,
        "type": "zones_owned",
    },
    {
        "id": "battle_today",
        "title": "Guerrero",
        "description": "Participa en 1 batalla hoy",
        "icon": "Swords",
        "color": "#00f0ff",
        "reward_power": 20,
        "reward_gold": 50,
        "target": 1,
        "type": "battles_today",
    },
]


def _get_claim(user_id: str, mission_id: str, date: str) -> dict | None:
    claim_key = f"{user_id}_{mission_id}_{date}"
    if USE_LOCAL:
        return store.doc_get(COLLECTION, claim_key)
    else:
        doc = db.collection(COLLECTION).document(claim_key).get()
        return doc.to_dict() if doc.exists else None


def _set_claim(user_id: str, mission_id: str, date: str) -> None:
    claim_key = f"{user_id}_{mission_id}_{date}"
    data = {"user_id": user_id, "mission_id": mission_id, "date": date,
            "claimed_at": datetime.utcnow().isoformat()}
    if USE_LOCAL:
        store.doc_set(COLLECTION, claim_key, data)
    else:
        db.collection(COLLECTION).document(claim_key).set(data)


def _compute_progress(mission: dict, user: dict, clan_id: str | None, today: str) -> int:
    mtype = mission["type"]

    if mtype == "steps_today":
        # Sum steps logged today from step_logs
        logs = repository_steps.get_user_history(user["id"], limit=50)
        total = sum(
            log.get("steps", 0) for log in logs
            if log.get("timestamp", "").startswith(today)
        )
        return total

    if mtype == "zones_owned":
        if not clan_id:
            return 0
        zones = repository_zones.list_zones()
        return sum(1 for z in zones if z.get("owner_clan_id") == clan_id)

    if mtype == "battles_today":
        if not clan_id:
            return 0
        battles = repository_battles.list_battles_by_clan(clan_id, limit=20)
        return sum(
            1 for b in battles
            if b.get("started_at", "").startswith(today)
        )

    return 0


@router.get("/")
def list_missions(current_user: dict = Depends(get_current_user)):
    today = _today()
    clan_id = current_user.get("clan_id")
    result = []
    for m in MISSION_CATALOGUE:
        progress = _compute_progress(m, current_user, clan_id, today)
        done = progress >= m["target"]
        claimed = _get_claim(current_user["id"], m["id"], today) is not None
        result.append({
            **m,
            "progress": min(progress, m["target"]),
            "done": done,
            "claimed": claimed,
            "claimable": done and not claimed,
        })
    return result


@router.post("/{mission_id}/claim", status_code=200)
def claim_mission(mission_id: str, current_user: dict = Depends(get_current_user)):
    today = _today()
    mission = next((m for m in MISSION_CATALOGUE if m["id"] == mission_id), None)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    if _get_claim(current_user["id"], mission_id, today):
        raise HTTPException(status_code=400, detail="Mission already claimed today")

    clan_id = current_user.get("clan_id")
    progress = _compute_progress(mission, current_user, clan_id, today)
    if progress < mission["target"]:
        raise HTTPException(status_code=400, detail="Mission not completed yet")

    # Grant reward
    repository_users.update_user(current_user["id"], {
        "power_points": current_user.get("power_points", 0) + mission["reward_power"],
        "gold": current_user.get("gold", 0) + mission["reward_gold"],
    })
    _set_claim(current_user["id"], mission_id, today)

    return {
        "mission_id": mission_id,
        "reward_power": mission["reward_power"],
        "reward_gold": mission["reward_gold"],
    }
