"""Router: sincronización de pasos, histórico y actualizaciones en tiempo real."""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from cloudrisk_api.configuracion import settings
from cloudrisk_api.database import pasos as pasos_repo, usuarios as usuarios_repo, clanes as clanes_repo, publicador_pubsub as pubsub_publisher
from cloudrisk_api.services.autenticacion import get_current_user

router = APIRouter(prefix="/steps", tags=["steps"])


class StepSync(BaseModel):
    steps: int
    lat: Optional[float] = None
    lng: Optional[float] = None


def _apply_step_rewards(user: dict, step_count: int) -> dict:
    """Convierte pasos en power+gold y persiste user, clan y log.

    Devuelve `{"power_earned", "gold_earned", "log"}` para que el caller
    pueda completar la respuesta. **No** publica a Pub/Sub — eso lo decide
    el caller (los dos puntos de entrada manejan el error de pubsub
    de forma distinta: el endpoint loguea, el WS lo silencia).
    """
    power_earned = step_count // settings.POWER_PER_STEPS
    gold_earned = step_count // 50  # 50 pasos = 1 moneda de oro
    log = pasos_repo.create_step_log(user["id"], step_count, power_earned)
    usuarios_repo.update_user(user["id"], {
        "steps_total": user.get("steps_total", 0) + step_count,
        "power_points": user.get("power_points", 0) + power_earned,
        "gold": user.get("gold", 0) + gold_earned,
    })
    if user.get("clan_id"):
        clan = clanes_repo.get_clan_by_id(user["clan_id"])
        if clan:
            clanes_repo.update_clan(user["clan_id"], {
                "total_power": clan.get("total_power", 0) + power_earned,
            })
    return {"power_earned": power_earned, "gold_earned": gold_earned, "log": log}


@router.post("/sync", status_code=201)
def sync_steps(data: StepSync, current_user: dict = Depends(get_current_user)):
    if data.steps <= 0:
        raise HTTPException(status_code=400, detail="Steps must be a positive number")
    rewards = _apply_step_rewards(current_user, data.steps)
    try:
        pubsub_publisher.publish_step_event(
            current_user["id"], data.steps, rewards["power_earned"],
        )
    except Exception as exc:
        logger.warning(f"Pub/Sub step publish failed for {current_user['id']}: {exc}")
    log = rewards["log"]
    log["gold_earned"] = rewards["gold_earned"]
    return log


@router.get("/history")
def get_step_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    return pasos_repo.get_user_history(current_user["id"], limit)


def _sync_step_update(user_id: str, step_count: int) -> None:
    if step_count <= 0:
        return
    user = usuarios_repo.get_user_by_id(user_id)
    if not user:
        return
    rewards = _apply_step_rewards(user, step_count)
    try:
        pubsub_publisher.publish_step_event(user_id, step_count, rewards["power_earned"])
    except Exception as exc:
        # Camino WS: no propagamos para no romper la actualización en vivo
        # si Pub/Sub no está disponible, pero dejamos traza para depurar.
        logger.warning(f"Pub/Sub step publish (WS path) failed for {user_id}: {exc}")


async def handle_step_update(user_id: str, steps: int) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_step_update, user_id, steps)
