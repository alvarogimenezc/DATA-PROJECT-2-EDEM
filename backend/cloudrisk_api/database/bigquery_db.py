"""
Acceso a BigQuery.
Solo escribe filas en las tablas de histórico.
"""
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery

from cloudrisk_api.config import settings


bq = bigquery.Client(project=settings.PROJECT_ID)
USER_ACTIONS_TABLE = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.{settings.BQ_USER_ACTIONS_TABLE}"


def insert_user_action(player_id: str, location_id: str, armies: int) -> str:
    """
    Inserta una fila en cloudrisk.user_actions.
    Devuelve el action_id generado.
    No lanza si BQ falla, solo loggea (no queremos tumbar la API por un fallo de histórico).
    """
    action_id = str(uuid.uuid4())
    row = {
        "action_id": action_id,
        "player_id": player_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "action_type": "place",
        "location_id": location_id,
        "armies": armies,
    }
    errors = bq.insert_rows_json(USER_ACTIONS_TABLE, [row], row_ids=[action_id])
    if errors:
        print(f"[bq] WARN insert user_actions falló: {errors}", flush=True)
    return action_id
