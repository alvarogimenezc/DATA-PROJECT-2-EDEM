"""
Acceso a Firestore.
Toda la interacción con Firestore se hace AQUÍ.
Los endpoints nunca tocan el SDK directamente.
"""
from datetime import datetime, timezone
from google.cloud import firestore

from cloudrisk_api.config import settings


db = firestore.Client(project=settings.PROJECT_ID)


class GameError(Exception):
    """Error de negocio del juego (no es un bug, es lógica)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def get_user_balance(player_id: str) -> dict:
    """Lee el documento user_balance/{player_id}. Devuelve dict vacío si no existe."""
    doc = db.collection(settings.COL_USER_BALANCE).document(player_id).get()
    return doc.to_dict() or {} if doc.exists else {}


def list_locations() -> list[dict]:
    """Devuelve todas las zonas con sus ejércitos actuales."""
    out = []
    for doc in db.collection(settings.COL_LOCATION_BALANCE).stream():
        data = doc.to_dict() or {}
        data["location_id"] = doc.id
        out.append(data)
    return out


def place_armies_transaction(player_id: str, location_id: str, armies: int) -> int:
    """
    Transacción atómica:
      - resta `armies` al jugador
      - suma `armies` a la zona (la crea si no existe)
    Devuelve los ejércitos restantes del jugador.
    Lanza GameError si no hay saldo o el jugador no existe.
    """
    user_ref = db.collection(settings.COL_USER_BALANCE).document(player_id)
    loc_ref = db.collection(settings.COL_LOCATION_BALANCE).document(location_id)

    @firestore.transactional
    def txn(transaction):
        user_snap = user_ref.get(transaction=transaction)
        if not user_snap.exists:
            raise GameError(404, f"player {player_id} no existe")
        user_data = user_snap.to_dict() or {}
        current = int(user_data.get("armies", 0))
        if current < armies:
            raise GameError(
                400, f"ejércitos insuficientes: tienes {current}, pides {armies}"
            )

        loc_snap = loc_ref.get(transaction=transaction)
        loc_data = (loc_snap.to_dict() or {}) if loc_snap.exists else {}
        loc_current = int(loc_data.get("armies", 0))

        now = datetime.now(timezone.utc)
        transaction.update(user_ref, {"armies": current - armies, "updated_at": now})
        if loc_snap.exists:
            transaction.update(
                loc_ref,
                {"armies": loc_current + armies, "owner": player_id, "updated_at": now},
            )
        else:
            transaction.set(
                loc_ref,
                {"armies": armies, "owner": player_id, "updated_at": now},
            )
        return current - armies

    return txn(db.transaction())
