"""Repository: operations for clans collection."""

from __future__ import annotations


import os
import uuid
from datetime import datetime

from cloudrisk_api.configuracion import settings

COLLECTION = settings.FIRESTORE_COLLECTION_CLANS
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=settings.PROJECT_ID)


def create_clan(name: str, color: str = "#ff0000", created_by: str = "") -> dict | None:
    if USE_LOCAL:
        existing = store.doc_query(COLLECTION, [("name", "==", name)], limit=1)
        if existing:
            return None
        clan_id = str(uuid.uuid4())
        clan_data = {
            "id": clan_id, "name": name, "color": color,
            "total_power": 0, "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
        }
        store.doc_set(COLLECTION, clan_id, clan_data)
        return clan_data
    else:
        existing = db.collection(COLLECTION).where("name", "==", name).limit(1).get()
        if list(existing):
            return None
        clan_id = str(uuid.uuid4())
        clan_data = {
            "id": clan_id, "name": name, "color": color,
            "total_power": 0, "created_by": created_by,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        db.collection(COLLECTION).document(clan_id).set(clan_data)
        return clan_data


def get_clan_by_id(clan_id: str) -> dict | None:
    if USE_LOCAL:
        return store.doc_get(COLLECTION, clan_id)
    else:
        doc = db.collection(COLLECTION).document(clan_id).get()
        return doc.to_dict() if doc.exists else None


def list_clans() -> list[dict]:
    if USE_LOCAL:
        clans = store.doc_stream(COLLECTION)
        users = store.doc_stream(settings.FIRESTORE_COLLECTION_USERS)
        for clan in clans:
            clan["member_count"] = sum(1 for u in users if u.get("clan_id") == clan["id"])
        return clans
    else:
        docs = db.collection(COLLECTION).stream()
        clans = []
        for doc in docs:
            clan = doc.to_dict()
            members = db.collection(settings.FIRESTORE_COLLECTION_USERS).where(
                "clan_id", "==", clan["id"]
            ).get()
            clan["member_count"] = len(list(members))
            clans.append(clan)
        return clans


def update_clan(clan_id: str, fields: dict) -> None:
    if USE_LOCAL:
        store.doc_update(COLLECTION, clan_id, fields)
    else:
        db.collection(COLLECTION).document(clan_id).update(fields)


def delete_clan(clan_id: str) -> None:
    if USE_LOCAL:
        store.doc_delete(COLLECTION, clan_id)
    else:
        db.collection(COLLECTION).document(clan_id).delete()
