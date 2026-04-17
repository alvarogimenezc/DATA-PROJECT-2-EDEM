"""Repository: operations for zones + geospatial detection with Shapely."""

from __future__ import annotations


import os
import threading
from shapely.geometry import Point, shape

from cloudrisk_api.configuracion import settings

COLLECTION = settings.FIRESTORE_COLLECTION_ZONES
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

# Mutex for local-store atomic conquer (replaces Firestore transactions in dev)
_conquer_lock = threading.Lock()

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=settings.PROJECT_ID)


def list_zones() -> list[dict]:
    if USE_LOCAL:
        return store.doc_stream(COLLECTION)
    else:
        return [doc.to_dict() for doc in db.collection(COLLECTION).stream()]


def get_zone_by_id(zone_id: str) -> dict | None:
    if USE_LOCAL:
        return store.doc_get(COLLECTION, zone_id)
    else:
        doc = db.collection(COLLECTION).document(zone_id).get()
        return doc.to_dict() if doc.exists else None


def update_zone(zone_id: str, fields: dict) -> None:
    if USE_LOCAL:
        store.doc_update(COLLECTION, zone_id, fields)
    else:
        db.collection(COLLECTION).document(zone_id).update(fields)


def conquer_zone_atomic(zone_id: str, clan_id: str, conquered_at: str) -> bool:
    """
    Atomically claim a free zone for clan_id.
    Returns True if this caller won the race, False if another clan beat them to it.

    Local store: protected by a threading.Lock so concurrent in-process calls
    cannot both see owner=None and both succeed.

    Firestore: wrapped in a server-side transaction; if another writer commits
    first the transaction retries, reads the new owner, and returns False.
    """
    if USE_LOCAL:
        with _conquer_lock:
            zone = store.doc_get(COLLECTION, zone_id)
            if not zone:
                return False
            if zone.get("owner_clan_id") is not None:
                return False   # already taken (by us or an enemy)
            store.doc_update(COLLECTION, zone_id, {
                "owner_clan_id": clan_id,
                "conquered_at": conquered_at,
                "defense_level": 0,
            })
            return True
    else:
        zone_ref = db.collection(COLLECTION).document(zone_id)

        @firestore.transactional
        def _txn(transaction):
            snap = zone_ref.get(transaction=transaction)
            if not snap.exists:
                return False
            if snap.get("owner_clan_id") is not None:
                return False
            transaction.update(zone_ref, {
                "owner_clan_id": clan_id,
                "conquered_at": conquered_at,
                "defense_level": 0,
            })
            return True

        return _txn(db.transaction())


def resolve_combat_atomic(
    source_id: str,
    target_id: str,
    attacker_clan: str,
    expected_source_armies: int,
    expected_target_owner: str | None,
    expected_target_armies: int,
    new_source_armies: int,
    new_target_armies: int,
    conquered: bool,
    conquered_at: str,
) -> bool:
    """
    Apply the result of a combat to both zones atomically.
    Returns True if the transaction committed, False if another writer
    modified either zone between the handler's read and this call
    (caller should retry or surface a 409 Conflict to the user).

    Local store: single lock covers both docs.
    Firestore: 1 transaction, 2 writes. Retried automatically up to 5 times.
    """
    update_source = {"defense_level": max(0, new_source_armies)}
    if conquered:
        update_target = {
            "owner_clan_id": attacker_clan,
            "defense_level": new_target_armies,
            "conquered_at": conquered_at,
        }
    else:
        update_target = {"defense_level": new_target_armies}

    if USE_LOCAL:
        with _conquer_lock:
            source = store.doc_get(COLLECTION, source_id) or {}
            target = store.doc_get(COLLECTION, target_id) or {}
            # Optimistic concurrency — bail if state changed beneath us
            if int(source.get("defense_level") or 0) != expected_source_armies:
                return False
            if int(target.get("defense_level") or 0) != expected_target_armies:
                return False
            if (target.get("owner_clan_id") or None) != expected_target_owner:
                return False
            store.doc_update(COLLECTION, source_id, update_source)
            store.doc_update(COLLECTION, target_id, update_target)
            return True
    else:
        source_ref = db.collection(COLLECTION).document(source_id)
        target_ref = db.collection(COLLECTION).document(target_id)

        @firestore.transactional
        def _txn(transaction):
            s = source_ref.get(transaction=transaction)
            t = target_ref.get(transaction=transaction)
            if not s.exists or not t.exists:
                return False
            if int(s.get("defense_level") or 0) != expected_source_armies:
                return False
            if int(t.get("defense_level") or 0) != expected_target_armies:
                return False
            if (t.get("owner_clan_id") or None) != expected_target_owner:
                return False
            transaction.update(source_ref, update_source)
            transaction.update(target_ref, update_target)
            return True

        return _txn(db.transaction())


def find_zone_containing_point(lat: float, lng: float) -> dict | None:
    point = Point(lng, lat)
    zones = store.doc_stream(COLLECTION) if USE_LOCAL else [
        doc.to_dict() for doc in db.collection(COLLECTION).stream()
    ]
    for zone in zones:
        geojson = zone.get("geojson")
        if not geojson:
            continue
        try:
            polygon = shape(geojson)
            if polygon.contains(point):
                return zone
        except Exception:
            continue
    return None
