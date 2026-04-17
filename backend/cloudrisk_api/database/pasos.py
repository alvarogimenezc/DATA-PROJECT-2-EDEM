"""Repository: operations for step_logs collection."""

from __future__ import annotations


import os
import uuid
from datetime import datetime

from cloudrisk_api.configuracion import settings

COLLECTION = settings.FIRESTORE_COLLECTION_STEP_LOGS
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=settings.PROJECT_ID)


def create_step_log(user_id: str, steps: int, power_earned: int) -> dict:
    log_id = str(uuid.uuid4())
    log_data = {
        "id": log_id, "user_id": user_id, "steps": steps,
        "power_points_earned": power_earned,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if USE_LOCAL:
        store.doc_set(COLLECTION, log_id, log_data)
    else:
        db.collection(COLLECTION).document(log_id).set(log_data)
    return log_data


def get_user_history(user_id: str, limit: int = 20) -> list[dict]:
    if USE_LOCAL:
        return store.doc_query(
            COLLECTION, [("user_id", "==", user_id)],
            order_by="timestamp", descending=True, limit=limit
        )
    else:
        docs = (
            db.collection(COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit).stream()
        )
        return [doc.to_dict() for doc in docs]
