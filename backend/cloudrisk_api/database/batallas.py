"""Repository: operations for battles collection."""

from __future__ import annotations


import os
import uuid
from datetime import datetime, timedelta

from cloudrisk_api.configuracion import settings

COLLECTION = settings.FIRESTORE_COLLECTION_BATTLES
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=settings.PROJECT_ID)


def create_battle(zone_id: str, attacker_clan_id: str, defender_clan_id: str | None,
                  attacker_power: int, defender_power: int) -> dict:
    battle_id = str(uuid.uuid4())
    now = datetime.utcnow()
    battle_data = {
        "id": battle_id, "zone_id": zone_id,
        "attacker_clan_id": attacker_clan_id,
        "defender_clan_id": defender_clan_id,
        "started_at": now.isoformat(),
        "ends_at": (now + timedelta(hours=settings.BATTLE_DURATION_HOURS)).isoformat(),
        "result": "ongoing",
        "attacker_power": attacker_power,
        "defender_power": defender_power,
        "loot": {},
    }
    if USE_LOCAL:
        store.doc_set(COLLECTION, battle_id, battle_data)
    else:
        db.collection(COLLECTION).document(battle_id).set(battle_data)
    return battle_data


def get_battle_by_id(battle_id: str) -> dict | None:
    if USE_LOCAL:
        return store.doc_get(COLLECTION, battle_id)
    else:
        doc = db.collection(COLLECTION).document(battle_id).get()
        return doc.to_dict() if doc.exists else None


def list_ongoing_battles() -> list[dict]:
    if USE_LOCAL:
        return store.doc_query(COLLECTION, [("result", "==", "ongoing")])
    else:
        docs = db.collection(COLLECTION).where("result", "==", "ongoing").stream()
        return [doc.to_dict() for doc in docs]


def get_ongoing_battle_in_zone(zone_id: str) -> dict | None:
    if USE_LOCAL:
        results = store.doc_query(COLLECTION, [
            ("zone_id", "==", zone_id), ("result", "==", "ongoing")
        ], limit=1)
        return results[0] if results else None
    else:
        docs = (
            db.collection(COLLECTION)
            .where("zone_id", "==", zone_id)
            .where("result", "==", "ongoing")
            .limit(1).get()
        )
        for doc in docs:
            return doc.to_dict()
        return None


def update_battle(battle_id: str, fields: dict) -> None:
    if USE_LOCAL:
        store.doc_update(COLLECTION, battle_id, fields)
    else:
        db.collection(COLLECTION).document(battle_id).update(fields)


def list_battles_by_clan(clan_id: str, limit: int = 10) -> list[dict]:
    """Return the most recent battles where clan was attacker or defender."""
    if USE_LOCAL:
        all_battles = store.doc_stream(COLLECTION)
        results = [
            b for b in all_battles
            if b.get("attacker_clan_id") == clan_id or b.get("defender_clan_id") == clan_id
        ]
        results.sort(key=lambda b: b.get("started_at", ""), reverse=True)
        return results[:limit]
    else:
        # Firestore doesn't support OR queries natively — run two queries and merge
        a_docs = (
            db.collection(COLLECTION)
            .where("attacker_clan_id", "==", clan_id)
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit).stream()
        )
        d_docs = (
            db.collection(COLLECTION)
            .where("defender_clan_id", "==", clan_id)
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit).stream()
        )
        seen, results = set(), []
        for doc in list(a_docs) + list(d_docs):
            d = doc.to_dict()
            if d["id"] not in seen:
                seen.add(d["id"])
                results.append(d)
        results.sort(key=lambda b: b.get("started_at", ""), reverse=True)
        return results[:limit]
