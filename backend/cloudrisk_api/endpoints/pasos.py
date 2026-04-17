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


@router.post("/sync", status_code=201)
def sync_steps(data: StepSync, current_user: dict = Depends(get_current_user)):
    if data.steps <= 0:
        raise HTTPException(status_code=400, detail="Steps must be a positive number")
    power_earned = data.steps // settings.POWER_PER_STEPS
    gold_earned = data.steps // 50  # 50 pasos = 1 moneda de oro
    log = pasos_repo.create_step_log(current_user["id"], data.steps, power_earned)
    usuarios_repo.update_user(current_user["id"], {
        "steps_total": current_user.get("steps_total", 0) + data.steps,
        "power_points": current_user.get("power_points", 0) + power_earned,
        "gold": current_user.get("gold", 0) + gold_earned,
    })
    if current_user.get("clan_id"):
        clan = clanes_repo.get_clan_by_id(current_user["clan_id"])
        if clan:
            clanes_repo.update_clan(current_user["clan_id"], {
                "total_power": clan.get("total_power", 0) + power_earned,
            })
    try:
        pubsub_publisher.publish_step_event(current_user["id"], data.steps, power_earned)
    except Exception as exc:
        logger.warning(f"Pub/Sub step publish failed for {current_user['id']}: {exc}")
    log["gold_earned"] = gold_earned
    return log


@router.get("/history")
def get_step_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    return pasos_repo.get_user_history(current_user["id"], limit)


@router.get("/realtime-ingestion-status")
def realtime_ingestion_status(current_user: dict = Depends(get_current_user)):
    """What the frontend uses to show "🛰️ Ingesta en vivo" widget.

    Returns, for the logged-in player:

      - ``last_scored_at`` — cuándo corrió el hourly_scorer por última vez.
      - ``today_real_steps`` — suma de pasos reales (source="real") ingeridos hoy.
      - ``next_scoring_in_minutes`` — cuánto falta para la próxima pasada.
      - ``ingestion_sources`` — desglose por origen (real / walker / backend_sync).

    Es la ventana que hace VISIBLE al usuario que el sistema está corriendo
    en vivo — sin esta API, un jugador no sabría si su ingesta de random_tracker
    funcionó o no hasta el día siguiente.
    """
    import os
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    next_top_of_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))

    # Si tenemos cliente BQ a mano, resumimos la ingesta de hoy. Fallback al
    # store en memoria en modo local/dev.
    status: dict = {
        "player_id": current_user["id"],
        "server_time": now.isoformat(),
        "next_scoring_in_minutes": int((next_top_of_hour - now).total_seconds() // 60),
        "ingestion_sources": {},
        "today_real_steps": 0,
        "last_scored_at": current_user.get("last_scored_at"),
    }

    use_local = os.environ.get("USE_LOCAL_STORE", "0") == "1"
    if use_local:
        # Best effort en memoria: cuenta step_logs de hoy.
        today_iso = now.strftime("%Y-%m-%d")
        logs = pasos_repo.get_user_history(current_user["id"], limit=500)
        status["today_real_steps"] = sum(
            int(l.get("steps", 0)) for l in logs if l.get("timestamp", "").startswith(today_iso)
        )
        status["ingestion_sources"] = {"backend_sync": status["today_real_steps"]}
        return status

    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=settings.PROJECT_ID)
        dataset = os.environ.get("BQ_DATASET", "cloudrisk")
        q = f"""
          SELECT COALESCE(source, 'unknown') AS source, SUM(steps_delta) AS total
            FROM `{settings.PROJECT_ID}.{dataset}.player_movements_raw`
           WHERE player_id = @pid
             AND DATE(ts) = CURRENT_DATE()
           GROUP BY source
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("pid", "STRING", current_user["id"])
        ])
        for row in bq.query(q, job_config=job_config).result():
            src = row["source"]
            status["ingestion_sources"][src] = int(row["total"] or 0)
        status["today_real_steps"] = status["ingestion_sources"].get("real", 0)
    except Exception as exc:
        logger.warning(f"BQ ingestion status lookup failed: {exc}")
        status["bq_error"] = str(exc)

    return status


def _sync_step_update(user_id: str, step_count: int) -> None:
    if step_count <= 0:
        return
    power_earned = step_count // settings.POWER_PER_STEPS
    gold_earned = step_count // 50
    pasos_repo.create_step_log(user_id, step_count, power_earned)
    user = usuarios_repo.get_user_by_id(user_id)
    if not user:
        return
    usuarios_repo.update_user(user_id, {
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
    try:
        pubsub_publisher.publish_step_event(user_id, step_count, power_earned)
    except Exception:
        pass


async def handle_step_update(user_id: str, steps: int) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_step_update, user_id, steps)
