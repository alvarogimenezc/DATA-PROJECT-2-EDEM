"""
In-memory storage backend for local development without GCP emulators.
Replaces Firestore client with a dict-based store.
Activate by setting environment variable: USE_LOCAL_STORE=1
"""

import uuid
import copy
from datetime import datetime
from typing import Optional, List

# ── In-memory collections ──
_store: dict[str, dict[str, dict]] = {
    "users": {},
    "clans": {},
    "zones": {},
    "battles": {},
    "step_logs": {},
}

# ── Pub/Sub log ──
_pubsub_log: list[dict] = []


def _now_iso():
    return datetime.utcnow().isoformat()


# ══════════════════════════════════════════════════
#  Generic CRUD
# ══════════════════════════════════════════════════

def doc_set(collection: str, doc_id: str, data: dict):
    """Set a document in a collection."""
    _store.setdefault(collection, {})[doc_id] = copy.deepcopy(data)


def doc_get(collection: str, doc_id: str) -> Optional[dict]:
    """Get a document by ID."""
    doc = _store.get(collection, {}).get(doc_id)
    return copy.deepcopy(doc) if doc else None


def doc_update(collection: str, doc_id: str, fields: dict):
    """Update fields on an existing document."""
    doc = _store.get(collection, {}).get(doc_id)
    if doc:
        doc.update(fields)


def doc_delete(collection: str, doc_id: str):
    """Delete a document from a collection."""
    _store.get(collection, {}).pop(doc_id, None)


def doc_stream(collection: str) -> List[dict]:
    """Return all documents in a collection."""
    return [copy.deepcopy(d) for d in _store.get(collection, {}).values()]


def doc_query(collection: str, filters: list[tuple], order_by: Optional[str] = None,
              descending: bool = False, limit: Optional[int] = None) -> List[dict]:
    """
    Query documents with filters: [(field, op, value), ...]
    Only supports '==' operator for simplicity.
    """
    results = []
    for doc in _store.get(collection, {}).values():
        match = True
        for field, op, value in filters:
            if op == "==" and doc.get(field) != value:
                match = False
                break
        if match:
            results.append(copy.deepcopy(doc))

    if order_by:
        results.sort(key=lambda d: d.get(order_by, ""), reverse=descending)

    if limit:
        results = results[:limit]

    return results


# ══════════════════════════════════════════════════
#  Pub/Sub mock
# ══════════════════════════════════════════════════

def pubsub_publish(topic: str, message: dict):
    """Log a pub/sub message (no-op in local mode)."""
    _pubsub_log.append({"topic": topic, "message": message, "timestamp": _now_iso()})


# ══════════════════════════════════════════════════
#  Seed data: Valencia zones
# ══════════════════════════════════════════════════

def _z(zone_id, name, value):
    return {"id": zone_id, "name": name, "owner_clan_id": None, "defense_level": 0, "value": value, "conquered_at": None, "geojson": None}


# Names match OSM GeoJSON (valencia_districts.geojson) for correct frontend name-matching
VALENCIA_ZONES = [
    # Ciutat Vella
    _z("zona-el-carme",            "el Carme",                    8),
    _z("zona-la-xerea",            "la Xerea",                    5),
    _z("zona-la-seu",              "la Seu",                      9),
    _z("zona-el-pilar",            "el Pilar",                    6),
    _z("zona-sant-francesc",       "Sant Francesc",               7),
    _z("zona-el-mercat",           "el Mercat",                   7),
    # Eixample
    _z("zona-russafa",             "Russafa",                     8),
    _z("zona-el-pla-del-remei",    "el Pla del Remei",            6),
    _z("zona-gran-via",            "Gran Via",                    6),
    # Extramurs
    _z("zona-arrancapins",         "Arrancapins",                 5),
    _z("zona-la-petxina",          "la Petxina",                  5),
    _z("zona-la-roqueta",          "la Roqueta",                  5),
    _z("zona-el-botanic",          "el Botànic",                  5),
    _z("zona-nou-moles",           "Nou Moles",                   5),
    _z("zona-soternes",            "Soternes",                    4),
    _z("zona-tres-forques",        "Tres Forques",                4),
    _z("zona-la-fontsanta",        "la Fontsanta",                4),
    _z("zona-la-llum",             "la Llum",                     4),
    # Campanar
    _z("zona-campanar",            "Campanar",                    5),
    _z("zona-les-tendetes",        "les Tendetes",                4),
    _z("zona-el-calvari",          "el Calvari",                  3),
    _z("zona-sant-pau",            "Sant Pau",                    5),
    # La Saidia
    _z("zona-marxalenes",          "Marxalenes",                  4),
    _z("zona-morvedre",            "Morvedre",                    4),
    _z("zona-trinitat",            "Trinitat",                    4),
    _z("zona-tormos",              "Tormos",                      4),
    _z("zona-sant-antoni",         "Sant Antoni",                 5),
    # El Pla del Real
    _z("zona-exposicio",           "Exposició",                   5),
    _z("zona-mestalla",            "Mestalla",                    6),
    _z("zona-jaume-roig",          "Jaume Roig",                  5),
    _z("zona-ciutat-universitaria","Ciutat Universitària",        6),
    # Olivereta
    _z("zona-nou-moles-2",         "Favara",                      4),
    _z("zona-safranar",            "Safranar",                    4),
    _z("zona-vara-de-quart",       "Vara de Quart",               4),
    _z("zona-sant-isidre",         "Sant Isidre",                 4),
    # Patraix
    _z("zona-patraix",             "Patraix",                     5),
    _z("zona-cami-real",           "Camí Real",                   4),
    _z("zona-sant-marcelli",       "Sant Marcel·lí",              4),
    _z("zona-la-creu-coberta",     "la Creu Coberta",             5),
    _z("zona-l-hort-de-senabre",   "l'Hort de Senabre",          4),
    _z("zona-la-raiosa",           "la Raïosa",                   4),
    # Jesus
    _z("zona-malilla",             "Malilla",                     5),
    _z("zona-en-corts",            "En Corts",                    4),
    _z("zona-montolivet",          "Montolivet",                  4),
    _z("zona-la-fonteta",          "la Fonteta de Sant Lluís",    4),
    _z("zona-na-rovella",          "Na Rovella",                  4),
    _z("zona-la-punta",            "la Punta",                    4),
    _z("zona-ciutat-arts",         "Ciutat de les Arts i de les Ciències", 5),
    # Quatre Carreres
    _z("zona-natzaret",            "Natzaret",                    4),
    _z("zona-pinedo",              "Pinedo",                      3),
    _z("zona-el-castellar",        "el Castellar - l'Oliveral",   3),
    _z("zona-el-forn-d-alcedo",    "el Forn d'Alcedo",            3),
    _z("zona-la-torre",            "la Torre",                    3),
    _z("zona-faitanar",            "Faitanar",                    2),
    # Poblats Maritims
    _z("zona-el-grau",             "el Grau",                     5),
    _z("zona-el-cabanyal",         "el Cabanyal - el Canyamelar", 6),
    _z("zona-la-malva-rosa",       "la Malva-rosa",               4),
    _z("zona-betero",              "Beteró",                      4),
    _z("zona-natzaret-2",          "la Creu del Grau",            4),
    _z("zona-cami-fondo",          "Camí Fondo",                  4),
    _z("zona-penya-roja",          "Penya-roja",                  4),
    _z("zona-albors",              "Albors",                      4),
    _z("zona-la-carrasca",         "la Carrasca",                 4),
    _z("zona-aiora",               "Aiora",                       4),
    _z("zona-la-vega-baixa",       "la Vega Baixa",               4),
    _z("zona-l-amistat",           "l'Amistat",                   4),
    _z("zona-ciutat-jardi",        "Ciutat Jardí",                4),
    _z("zona-l-illa-perduda",      "l'Illa Perduda",              4),
    # Rascanya
    _z("zona-els-orriols",         "els Orriols",                 4),
    _z("zona-torrefiel",           "Torrefiel",                   4),
    _z("zona-sant-llorenc",        "Sant Llorenç",                4),
    # Benimaclet
    _z("zona-benimaclet",          "Benimaclet",                  5),
    _z("zona-cami-de-vera",        "Camí de Vera",                4),
    # Benicalap
    _z("zona-benicalap",           "Benicalap",                   4),
    _z("zona-ciutat-fallera",      "Ciutat Fallera",              4),
    # Poblats del Nord
    _z("zona-massarojos",          "Massarojos",                  3),
    _z("zona-benifaraig",          "Benifaraig",                  3),
    _z("zona-borbot",              "Borbotó",                     3),
    _z("zona-mauella",             "Mauella",                     3),
    _z("zona-carpesa",             "Carpesa",                     3),
    _z("zona-cases-de-barcena",    "les Cases de Bàrcena",        3),
    _z("zona-poble-nou",           "Poble Nou",                   3),
    # Poblats de l'Oest
    _z("zona-beniferri",           "Beniferri",                   3),
    _z("zona-benimàmet",           "Benimàmet",                   4),
    # Poblats del Sud
    _z("zona-el-palmar",           "el Palmar",                   2),
    _z("zona-el-saler",            "el Saler",                    2),
]


def seed_zones():
    """Load Valencia zones into the in-memory store (names aligned with OSM GeoJSON)."""
    for zone in VALENCIA_ZONES:
        doc_set("zones", zone["id"], zone)
    print(f"[LOCAL MODE] Seeded {len(VALENCIA_ZONES)} Valencia zones.")


def seed_demo_players():
    """Load the 4 demo players from data/players.json (file: <repo-root>/data/players.json).

    Idempotent: skips players whose email is already in the store. Bcrypt-hashes
    the plaintext password from the JSON. Useful for both local-only demos and
    as the canonical source for scripts/sembrar_firestore.py.
    """
    import json
    import uuid
    from datetime import datetime
    from pathlib import Path

    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # data/players.json lives at repo root: backend/cloudrisk_api/database/almacen_en_memoria.py
    # → backend/cloudrisk_api/database → backend/cloudrisk_api → backend → repo root.
    seed_path = Path(__file__).resolve().parents[3] / "data" / "players.json"
    if not seed_path.exists():
        print(f"[LOCAL MODE] No demo players seed at {seed_path}, skipping.")
        return

    with seed_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    created = 0
    for p in payload.get("players", []):
        if doc_query("users", [("email", "==", p["email"])], limit=1):
            continue
        user_id = p.get("id") or str(uuid.uuid4())
        doc_set("users", user_id, {
            "id": user_id,
            "name": p["name"],
            "email": p["email"],
            "hashed_password": pwd_context.hash(p["password"]),
            "clan_id": None,
            "steps_total": 0,
            "power_points": 0,
            "gold": p.get("starting_gold", 0),
            "level": 1,
            "created_at": datetime.utcnow().isoformat(),
            # Game-specific extras (not part of standard user; consumed by the
            # game logic if present, harmless if not).
            "clan_color": p.get("clan_color"),
            "spawn_zone": p.get("spawn_zone"),
            "starting_armies": p.get("starting_armies", 0),
        })
        created += 1
    print(f"[LOCAL MODE] Seeded {created} demo players (skipped {len(payload.get('players', [])) - created} duplicates).")
