#!/usr/bin/env python3
"""
puntuador_horario.py — Cloud Run Service invocado por Cloud Scheduler cada hora.

Qué hace
========
1. Lee de BigQuery todos los pasos de la **última hora** (tabla
   `cloudrisk.player_movements_raw` → alimentada por la pipeline de
   Noelia+Martha con los mensajes del topic `player-movements`).
2. Consulta `environmental_factors` de la MISMA ventana para sacar el
   multiplicador ambiental medio (aire × clima) por zona.
3. Aplica la regla de scoring:

        puntos = pasos × multiplicador_ambiental
        armies_ganados = puntos // 10          # 1 army por cada 10 pts
        gold_ganado    = puntos // 100         # 1 gold por cada 100 pts

4. Actualiza `user_balance/{player_id}` en Firestore:

        armies       += armies_ganados
        gold         += gold_ganado
        total_steps  += pasos_hora
        last_scored_at = now()

Por qué horario
===============
- Scoring cada hora = feedback rápido ("mira, los 500 pasos de las 10-11
  ya te dan 3 armies").
- Sin romper el presupuesto: BQ query escanea ~1 MB/hora → ~720 MB/mes →
  < 1 céntimo de BQ al mes.

Triggers
========
Este servicio expone `POST /run` que Cloud Scheduler invoca con OIDC auth.
También se puede llamar a mano:

    curl -X POST https://cloudrisk-hourly-scorer-xxx.run.app/run \
      -H "Authorization: Bearer $(gcloud auth print-identity-token)"

Variables de entorno
====================
    PROJECT_ID       (requerido)
    BQ_DATASET       (default: cloudrisk)
    STEPS_TABLE      (default: player_movements_raw)
    ENV_TABLE        (default: environmental_factors)
    SCORING_WINDOW_MIN (default: 60)
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def score_window(project: str, window_min: int = 60) -> dict:
    """Calcula el delta de scoring para los últimos `window_min` minutos.

    Devuelve un dict que mapea player_id → dict de delta. El caller lo
    persiste en Firestore. Mantener esta función pura la hace testeable sin GCP.
    """
    from google.cloud import bigquery
    bq = bigquery.Client(project=project)

    dataset = os.environ.get("BQ_DATASET", "cloudrisk")
    steps_tbl = os.environ.get("STEPS_TABLE", "player_movements_raw")
    env_tbl = os.environ.get("ENV_TABLE", "environmental_factors")

    # 1) Suma los pasos por jugador en la ventana
    steps_query = f"""
        SELECT player_id,
               SUM(steps_delta) AS steps_hour,
               AVG(latitude)    AS avg_lat,
               AVG(longitude)   AS avg_lon
          FROM `{project}.{dataset}.{steps_tbl}`
         WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {window_min} MINUTE)
         GROUP BY player_id
         HAVING steps_hour > 0
    """
    print(f"[scorer] steps query: {steps_query.strip()}")

    # 2) Multiplicador ambiental medio en la misma ventana
    env_query = f"""
        SELECT AVG(multiplier) AS mult_avg
          FROM `{project}.{dataset}.{env_tbl}`
         WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {window_min} MINUTE)
    """
    print(f"[scorer] env query: {env_query.strip()}")

    # Ejecuta en paralelo mentalmente; los jobs de BQ son independientes.
    steps_rows = list(bq.query(steps_query).result())
    env_rows = list(bq.query(env_query).result())
    mult = float(env_rows[0]["mult_avg"]) if env_rows and env_rows[0]["mult_avg"] is not None else 1.0
    print(f"[scorer] environmental multiplier average = {mult:.3f}")

    delta_per_player: dict[str, dict] = {}
    for row in steps_rows:
        steps = int(row["steps_hour"])
        points = int(steps * mult)
        delta_per_player[row["player_id"]] = {
            "steps_hour": steps,
            "multiplier": mult,
            "points": points,
            "armies_delta": points // 10,
            "gold_delta": points // 100,
        }
    return delta_per_player


def apply_to_firestore(project: str, deltas: dict) -> None:
    """Actualiza ambas colecciones:

    - ``user_balance/`` (contrato del EQUIPO, lo que lee la pipeline compartida).
    - ``users/`` (backend CloudRISK, lo que muta `/steps/sync`).

    Escribir en ambas significa que el scorer horario es la única fuente de
    verdad para el scoring de pasos reales, Y la UI del juego (que lee
    `users/`) ve los armies/gold recién ganados segundos después de que el
    scorer termine.
    """
    from google.cloud import firestore
    db = firestore.Client(project=project)
    now = datetime.now(timezone.utc)

    for player_id, d in deltas.items():
        # Colección del contrato del equipo
        bal_ref = db.collection("user_balance").document(player_id)
        bal_current = bal_ref.get().to_dict() or {}
        bal_ref.set({
            "armies": int(bal_current.get("armies", 0)) + int(d["armies_delta"]),
            "gold": int(bal_current.get("gold", 0)) + int(d["gold_delta"]),
            "total_steps": int(bal_current.get("total_steps", 0)) + int(d["steps_hour"]),
            "last_scored_at": now,
        }, merge=True)

        # Colección del juego CloudRISK (lo que lee el backend en /me, /leaderboard)
        user_ref = db.collection("users").document(player_id)
        user_current = user_ref.get().to_dict() or {}
        user_ref.set({
            "steps_total": int(user_current.get("steps_total", 0)) + int(d["steps_hour"]),
            "power_points": int(user_current.get("power_points", 0)) + int(d["points"]),
            "gold": int(user_current.get("gold", 0)) + int(d["gold_delta"]),
            "last_scored_at": now,
        }, merge=True)

        # Fila de auditoría inmutable para que el dashboard pueda pintar "puntos por hora por jugador"
        db.collection("hourly_score_log").add({
            "player_id": player_id,
            "ts": now,
            **d,
        })

        print(f"  {player_id}: +{d['steps_hour']} steps → +{d['armies_delta']} armies, +{d['gold_delta']} gold, +{d['points']} power (mult={d['multiplier']:.2f})")


def _handler_body(project: str, window_min: int) -> dict:
    deltas = score_window(project, window_min)
    if deltas:
        apply_to_firestore(project, deltas)
    return {
        "window_min": window_min,
        "players_scored": len(deltas),
        "deltas": deltas,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Servidor HTTP (Cloud Run) — FastAPI si está disponible, fallback a http.server
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="cloudrisk-hourly-scorer")

    @app.get("/")
    def root() -> dict:
        return {"service": "cloudrisk-hourly-scorer", "status": "ready"}

    @app.post("/run")
    def run() -> dict:
        project = os.environ.get("PROJECT_ID")
        if not project:
            raise HTTPException(500, "PROJECT_ID not set")
        window = int(os.environ.get("SCORING_WINDOW_MIN", "60"))
        return _handler_body(project, window)

except ImportError:
    app = None
    print("[scorer] fastapi no disponible — script corre en modo CLI únicamente")


def main_cli() -> None:
    project = os.environ.get("PROJECT_ID")
    if not project:
        sys.exit("PROJECT_ID env var requerido")
    window = int(os.environ.get("SCORING_WINDOW_MIN", "60"))
    result = _handler_body(project, window)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    # Cuando corres el contenedor, Cloud Run usa el uvicorn de Dockerfile.
    # Llamada directa `python puntuador_horario.py` corre la versión CLI.
    main_cli()
