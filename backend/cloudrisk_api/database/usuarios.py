"""Repository: operations for users collection."""

from __future__ import annotations


import os
import uuid
from datetime import datetime
from passlib.context import CryptContext

from cloudrisk_api.configuracion import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
COLLECTION = settings.FIRESTORE_COLLECTION_USERS
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import firestore
    db = firestore.Client(project=settings.PROJECT_ID)


def create_user(name: str, email: str, password: str) -> dict:
    """Create a new user document."""
    if USE_LOCAL:
        existing = store.doc_query(COLLECTION, [("email", "==", email)], limit=1)
        if existing:
            return None
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id, "name": name, "email": email,
            "hashed_password": pwd_context.hash(password),
            "clan_id": None, "steps_total": 0, "power_points": 0,
            "gold": 0, "level": 1, "created_at": datetime.utcnow().isoformat(),
        }
        store.doc_set(COLLECTION, user_id, user_data)
        safe = {k: v for k, v in user_data.items() if k != "hashed_password"}
        return safe
    else:
        existing = db.collection(COLLECTION).where("email", "==", email).limit(1).get()
        if list(existing):
            return None
        user_id = str(uuid.uuid4())
        # NOTE: Avoid returning Firestore SERVER_TIMESTAMP sentinel directly.
        # FastAPI can't JSON-serialize that object; store a concrete datetime instead.
        user_data = {
            "id": user_id, "name": name, "email": email,
            "hashed_password": pwd_context.hash(password),
            "clan_id": None, "steps_total": 0, "power_points": 0,
            "gold": 0, "level": 1, "created_at": firestore.SERVER_TIMESTAMP,
        }
        db.collection(COLLECTION).document(user_id).set(user_data)
        user_data.pop("hashed_password")
        user_data["created_at"] = datetime.utcnow().isoformat()
        return user_data


def get_user_by_email(email: str) -> dict | None:
    if USE_LOCAL:
        results = store.doc_query(COLLECTION, [("email", "==", email)], limit=1)
        return results[0] if results else None
    else:
        docs = db.collection(COLLECTION).where("email", "==", email).limit(1).get()
        for doc in docs:
            return doc.to_dict()
        return None


def get_user_by_id(user_id: str) -> dict | None:
    if USE_LOCAL:
        return store.doc_get(COLLECTION, user_id)
    else:
        doc = db.collection(COLLECTION).document(user_id).get()
        return doc.to_dict() if doc.exists else None


def update_user(user_id: str, fields: dict) -> None:
    if USE_LOCAL:
        store.doc_update(COLLECTION, user_id, fields)
    else:
        db.collection(COLLECTION).document(user_id).update(fields)


def list_users_by_clan(clan_id: str) -> list[dict]:
    if USE_LOCAL:
        return store.doc_query(COLLECTION, [("clan_id", "==", clan_id)])
    else:
        docs = db.collection(COLLECTION).where("clan_id", "==", clan_id).get()
        return [d.to_dict() for d in docs]


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def list_all_users() -> list[dict]:
    """Return all users (stripped of password). Used for bulk operations like decay."""
    if USE_LOCAL:
        users = store.doc_stream(COLLECTION)
    else:
        users = [doc.to_dict() for doc in db.collection(COLLECTION).stream()]
    return [{k: v for k, v in u.items() if k != "hashed_password"} for u in users]


def list_users_top(limit: int = 10) -> list[dict]:
    """Return top users by power_points, stripped of sensitive fields."""
    SAFE_FIELDS = {"id", "name", "clan_id", "steps_total", "power_points", "gold", "level"}
    if USE_LOCAL:
        users = store.doc_query(COLLECTION, [], order_by="power_points", descending=True, limit=limit)
    else:
        docs = (
            db.collection(COLLECTION)
            .order_by("power_points", direction="DESCENDING")
            .limit(limit).stream()
        )
        users = [doc.to_dict() for doc in docs]
    return [{k: v for k, v in u.items() if k in SAFE_FIELDS} for u in users]
