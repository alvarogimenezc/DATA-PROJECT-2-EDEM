"""
CloudRISK API — endpoints de analítica sobre BigQuery.

Sustituyen al antiguo dashboard Streamlit. El pipeline Dataflow unificado
escribe `player_scoring_events` y `environmental_factors`; estos endpoints
hacen las consultas analíticas pesadas (top pasos del mes, top días de lluvia,
top días de mala calidad del aire e histórico por usuario) y las sirven al
frontend React.

Nota: las queries se cachean 60 s en memoria por si el frontend hace polling.
BigQuery cobra por bytes escaneados, así que evitamos consultarlo en cada
request.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ─── Cache TTL en memoria ─────────────────────────────────────────────────────
_TTL_S = 60.0
_cache: dict[str, tuple[float, Any]] = {}


def _cached(key: str, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and (now - hit[0] < _TTL_S):
        return hit[1]
    data = fn()
    _cache[key] = (now, data)
    return data


# ─── Cliente BigQuery perezoso ────────────────────────────────────────────────
_bq_client = None


def _bq():
    global _bq_client
    if _bq_client is None:
        from google.cloud import bigquery
        _bq_client = bigquery.Client(project=os.environ.get("PROJECT_ID"))
    return _bq_client


def _dataset() -> str:
    return os.environ.get("BIGQUERY_DATASET", "cloudrisk")


def _project() -> str:
    return os.environ.get("PROJECT_ID", "cloudrisk-local")


def _run(query: str) -> list[dict]:
    """Ejecuta una query y devuelve filas como dicts serializables. Si BigQuery
    no está disponible (local sin credenciales), devuelve [] en lugar de 500."""
    try:
        rows = _bq().query(query).result()
    except Exception as exc:
        # El frontend debe poder pintar "sin datos aún" sin que el backend
        # devuelva 500. Logueamos y seguimos.
        print(f"[analytics] BigQuery unavailable: {exc}")
        return []
    out = []
    for r in rows:
        item = {}
        for k, v in dict(r).items():
            # Convierte TIMESTAMP/date a ISO
            item[k] = v.isoformat() if hasattr(v, "isoformat") else v
        out.append(item)
    return out


def _cached_bq_query(cache_key: str, sql: str) -> list[dict]:
    """Combina cache TTL + ejecución BQ en una sola llamada.

    Usado por todos los endpoints — evita el patrón repetido de definir un
    closure `q()` que llama a `_run(sql)` y envuelve con `_cached(key, q)`.
    """
    return _cached(cache_key, lambda: _run(sql))


# ─── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/top-steps-month")
def top_steps_month(limit: int = Query(10, ge=1, le=100)):
    """Top jugadores por pasos acumulados en los últimos 30 días."""
    sql = f"""
        SELECT player_id,
               SUM(steps_delta) AS steps_month,
               SUM(armies_earned) AS armies_month,
               SUM(distance_m) / 1000 AS km_month
          FROM `{_project()}.{_dataset()}.player_scoring_events`
         WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
         GROUP BY player_id
         ORDER BY steps_month DESC
         LIMIT {int(limit)}
    """
    return _cached_bq_query(f"top-steps-month:{limit}", sql)


@router.get("/top-rainy-days")
def top_rainy_days(limit: int = Query(10, ge=1, le=100)):
    """Top jugadores que más andan en días de tiempo malo.

    Un "día lluvioso" se identifica como aquellos donde el multiplicador
    weather medio fue < 1.0 (baseline). Cruza con player_scoring_events.
    """
    sql = f"""
        WITH rainy_days AS (
          SELECT DATE(ts) AS d
            FROM `{_project()}.{_dataset()}.environmental_factors`
           WHERE type = 'weather'
           GROUP BY d
          HAVING AVG(multiplier) < 1.0
        )
        SELECT p.player_id,
               SUM(p.steps_delta) AS steps_rainy,
               COUNT(DISTINCT DATE(p.ts)) AS rainy_days_active
          FROM `{_project()}.{_dataset()}.player_scoring_events` p
          JOIN rainy_days r ON DATE(p.ts) = r.d
         GROUP BY p.player_id
         ORDER BY steps_rainy DESC
         LIMIT {int(limit)}
    """
    return _cached_bq_query(f"top-rainy-days:{limit}", sql)


@router.get("/top-bad-air")
def top_bad_air(limit: int = Query(10, ge=1, le=100)):
    """Top jugadores activos en días de mala calidad del aire (multiplier < 0.9)."""
    sql = f"""
        WITH bad_air_days AS (
          SELECT DATE(ts) AS d
            FROM `{_project()}.{_dataset()}.environmental_factors`
           WHERE type = 'air_quality'
           GROUP BY d
          HAVING AVG(multiplier) < 0.9
        )
        SELECT p.player_id,
               SUM(p.steps_delta) AS steps_bad_air,
               COUNT(DISTINCT DATE(p.ts)) AS bad_air_days_active
          FROM `{_project()}.{_dataset()}.player_scoring_events` p
          JOIN bad_air_days b ON DATE(p.ts) = b.d
         GROUP BY p.player_id
         ORDER BY steps_bad_air DESC
         LIMIT {int(limit)}
    """
    return _cached_bq_query(f"top-bad-air:{limit}", sql)


@router.get("/user/{player_id}/history")
def user_history(player_id: str, days: int = Query(7, ge=1, le=90)):
    """Serie temporal (por día) del jugador: pasos, armies y distancia."""
    safe_pid = "".join(c for c in player_id if c.isalnum() or c in "-_")
    if not safe_pid:
        raise HTTPException(400, "player_id inválido")
    sql = f"""
        SELECT DATE(ts) AS day,
               SUM(steps_delta) AS steps,
               SUM(armies_earned) AS armies,
               SUM(distance_m) / 1000 AS km,
               COUNTIF(capped) AS capped_events
          FROM `{_project()}.{_dataset()}.player_scoring_events`
         WHERE player_id = '{safe_pid}'
           AND ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(days)} DAY)
         GROUP BY day
         ORDER BY day
    """
    return _cached_bq_query(f"user-history:{safe_pid}:{days}", sql)


@router.get("/anti-cheat-rejects")
def anti_cheat_rejects(limit: int = Query(50, ge=1, le=500)):
    """Últimos eventos rechazados por velocidad excesiva u otros motivos."""
    sql = f"""
        SELECT processed_at, source, reason, player_id
          FROM `{_project()}.{_dataset()}.dead_letter`
         WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
         ORDER BY processed_at DESC
         LIMIT {int(limit)}
    """
    return _cached_bq_query(f"anti-cheat:{limit}", sql)
