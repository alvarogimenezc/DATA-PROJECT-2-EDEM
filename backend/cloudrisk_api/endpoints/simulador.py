"""
Endpoint de simulación de bots disparado desde el frontend.

Se distingue del script `backend/simulador_bots.py`:
  - `simulador_bots.py` es un cliente HTTP que habla con la API como un
    jugador externo — ideal para stress tests y smoke tests en CI.
  - Este módulo se ejecuta DENTRO del backend, toca los repos directos
    (zonas_repo, usuarios_repo) y aplica cambios visibles al instante en
    el mapa del frontend. Es el botón "Simular bots" del lobby.

Cada llamada hace que los 3 demo-players que NO son el jugador actual
ejecuten N rondas de acciones. Cada acción elige, en este orden:

  1. Conquistar una zona libre (si queda alguna).
  2. Tomar una zona enemiga débil (defense_level <= 2) — simplificación
     de batalla: no hay dados, pero mantiene el principio de que sólo
     zonas poco defendidas caen rápido.
  3. Reforzar una zona propia aleatoria (+1 defense, cap MAX_ZONE_DEFENSE).

El resultado es un JSON con todas las acciones — el frontend lo muestra
en un toast/popover y llama a `onRefresh()` para repintar el mapa.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cloudrisk_api.configuracion import settings, MAX_ZONE_DEFENSE
from cloudrisk_api.database import zonas as zonas_repo, usuarios as usuarios_repo
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import estado_juego as game_state


router = APIRouter(prefix="/simulate_bots", tags=["simulation"])


class SimulateBotsRequest(BaseModel):
    rounds: int = Field(default=2, ge=1, le=10,
                         description="Acciones por bot (1-10). Default 2.")


def _choose_action(bot_id: str, zones: list[dict]) -> tuple[str, dict | None]:
    """Devuelve (tipo, zona_objetivo | None). Prioridad: conquer > attack > fortify.

    Implementado como función pura para que el orquestador pueda registrar
    la acción antes de persistirla — útil si mañana queremos publicar a
    Pub/Sub o a un WebSocket broadcast.
    """
    free = [z for z in zones if not z.get("owner_clan_id")]
    if free:
        return "conquer", random.choice(free)

    # Atacar una zona enemiga débil (defense_level <= 2)
    enemy_weak = [
        z for z in zones
        if z.get("owner_clan_id") and z.get("owner_clan_id") != bot_id
        and int(z.get("defense_level") or 0) <= 2
    ]
    if enemy_weak:
        return "attack", random.choice(enemy_weak)

    # Reforzar una propia
    mine = [z for z in zones if z.get("owner_clan_id") == bot_id]
    if mine:
        return "fortify", random.choice(mine)

    return "idle", None


def _apply_action(bot_id: str, action: str, zone: dict, now_iso: str) -> dict:
    """Persiste la acción y devuelve el registro para el log de retorno."""
    if action == "conquer":
        zonas_repo.update_zone(zone["id"], {
            "owner_clan_id": bot_id,
            "defense_level": settings.INITIAL_ARMIES_PER_ZONE,
            "conquered_at": now_iso,
        })
        return {"bot": bot_id, "action": "conquer", "zone_id": zone["id"],
                "zone_name": zone.get("name"), "new_defense": settings.INITIAL_ARMIES_PER_ZONE}

    if action == "attack":
        # Simplificación: zonas poco defendidas caen automáticamente y el
        # atacante se queda con el control + 1 tropa. No hay dados porque el
        # botón está pensado para animar la demo, no para jugar competitivo.
        zonas_repo.update_zone(zone["id"], {
            "owner_clan_id": bot_id,
            "defense_level": 1,
            "conquered_at": now_iso,
        })
        return {"bot": bot_id, "action": "attack", "zone_id": zone["id"],
                "zone_name": zone.get("name"), "prev_owner": zone.get("owner_clan_id"),
                "new_defense": 1}

    if action == "fortify":
        prev = int(zone.get("defense_level") or 0)
        new_def = min(MAX_ZONE_DEFENSE, prev + 1)
        zonas_repo.update_zone(zone["id"], {"defense_level": new_def})
        return {"bot": bot_id, "action": "fortify", "zone_id": zone["id"],
                "zone_name": zone.get("name"),
                "prev_defense": prev, "new_defense": new_def}

    return {"bot": bot_id, "action": "idle"}


@router.post("/run")
def run_simulation(
    req: SimulateBotsRequest = SimulateBotsRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Ejecuta `rounds` acciones por cada demo-bot que NO sea el usuario actual.

    Devuelve un resumen con la lista de acciones aplicadas. El frontend lo usa
    para refrescar el mapa y opcionalmente mostrar un resumen del turno.
    """
    bot_ids = [pid for pid in game_state.DEFAULT_PLAYER_ORDER if pid != current_user["id"]]
    if not bot_ids:
        raise HTTPException(status_code=400,
                            detail="No demo bots available (you are all four?)")

    now_iso = datetime.now(timezone.utc).isoformat()
    actions: list[dict] = []

    for _ in range(req.rounds):
        for bot_id in bot_ids:
            # Releemos zonas en cada paso para que los bots no pisen las acciones
            # del anterior bot (evita dos bots conquistando la misma zona libre).
            zones = zonas_repo.list_zones()
            kind, zone = _choose_action(bot_id, zones)
            if zone is None:
                actions.append({"bot": bot_id, "action": "idle"})
                continue
            actions.append(_apply_action(bot_id, kind, zone, now_iso))

    # Resumen por bot para que el frontend pinte un mini-card rápido.
    summary: dict[str, dict[str, int]] = {
        bot_id: {"conquer": 0, "attack": 0, "fortify": 0, "idle": 0}
        for bot_id in bot_ids
    }
    for a in actions:
        summary[a["bot"]][a["action"]] = summary[a["bot"]].get(a["action"], 0) + 1

    return {
        "status": "ok",
        "triggered_by": current_user["id"],
        "rounds": req.rounds,
        "bots": bot_ids,
        "total_actions": len(actions),
        "actions": actions,
        "summary": summary,
    }
