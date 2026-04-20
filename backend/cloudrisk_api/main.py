"""
CloudRISK / CloudRISK API — punto de entrada FastAPI.
Expone los endpoints REST del juego bajo /api/v1 y un WebSocket en
/ws/{user_id}. Implementa el contrato de 4 endpoints del equipo desde
alvarogimenezc/DATA-PROJECT-2-EDEM más 25+ rutas internas para la
experiencia enriquecida (combate con dados, turnos, misiones, clanes, etc.).

EDEM. Máster Big Data & Cloud 2025/2026
Profesores: Javi Briones y Adriana Campos
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from cloudrisk_api.endpoints import (
    analiticas as analytics,
    ejercitos as armies,
    batallas as battles,
    clanes as clans,
    misiones as missions,
    multiplicadores as multipliers,
    pasos as steps,
    compatibilidad_equipo as team_compat,
    turno as turn,
    usuarios as users,
    zonas as zones,
    simulador as simulation,
)
from cloudrisk_api.services.gestor_websocket import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cloudrisk_api")

base_path = "/api/v1"
api_router = APIRouter(prefix=base_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Contexto de lifespan (reemplaza al deprecado @app.on_event('startup')).
    Ejecuta el seed al arrancar; no hace falta limpieza al apagar.
    """
    _run_startup_seed()
    yield


app = FastAPI(
    title="CloudRISK API",
    description="Juego de estrategia con geolocalización real — La ciudad es tu campo de batalla",
    docs_url=f"{base_path}/docs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: 'allow_origins=*' es incompatible con 'allow_credentials=True' (los navegadores
# lo rechazan). Como nuestro frontend no manda cookies (solo Bearer tokens en
# localStorage), vamos con credentials=False y orígenes permisivos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluye todos los routers bajo /api/v1
app.include_router(prefix=api_router.prefix, router=users.router)
app.include_router(prefix=api_router.prefix, router=clans.router)
app.include_router(prefix=api_router.prefix, router=zones.router)
app.include_router(prefix=api_router.prefix, router=steps.router)
app.include_router(prefix=api_router.prefix, router=armies.router)
app.include_router(prefix=api_router.prefix, router=multipliers.router)
app.include_router(prefix=api_router.prefix, router=turn.router)
app.include_router(prefix=api_router.prefix, router=team_compat.router)
app.include_router(prefix=api_router.prefix, router=missions.router)
app.include_router(prefix=api_router.prefix, router=battles.router)
app.include_router(prefix=api_router.prefix, router=analytics.router)
app.include_router(prefix=api_router.prefix, router=simulation.router)


def _seed_zones_firestore() -> None:
    """Siembra `VALENCIA_ZONES` en Firestore si la colección está vacía.

    Sólo se ejecuta cuando NO estamos en modo local (`USE_LOCAL_STORE != 1`).
    Si Firestore no responde (sin credenciales en dev), logueamos y seguimos
    — no es razón para tumbar el arranque del API.
    """
    try:
        from cloudrisk_api.database.almacen_en_memoria import VALENCIA_ZONES
        from cloudrisk_api.database import zonas as zonas_repo
        existing = zonas_repo.list_zones()
        if existing:
            print(f"[FIRESTORE] Zones already seeded ({len(existing)} found).")
            return
        from google.cloud import firestore
        db = firestore.Client(project=os.environ.get("PROJECT_ID", "cloudrisk-local"))
        col = os.environ.get("FIRESTORE_COLLECTION_ZONES", "zones")
        for zone in VALENCIA_ZONES:
            db.collection(col).document(zone["id"]).set(zone)
        print(f"[FIRESTORE] Seeded {len(VALENCIA_ZONES)} Valencia zones.")
    except Exception as e:
        print(f"[FIRESTORE] Zone seeding skipped: {e}")


def _seed_demo_players_firestore() -> None:
    """Siembra los 4 jugadores demo con IDs fijos en Firestore.

    Los IDs (`demo-player-001..004`) tienen que coincidir con el orden de
    turnos de `game_state.DEFAULT_PLAYER_ORDER`, por eso no se generan al
    vuelo. La password está hasheada con bcrypt para que el login funcione.
    """
    try:
        from datetime import datetime
        from passlib.context import CryptContext
        from google.cloud import firestore
        from cloudrisk_api.configuracion import settings

        DEMO_PLAYERS = [
            {"id": "demo-player-001", "name": "Comandante Norte", "email": "norte@cloudrisk.app", "password": "demo1234", "gold": 500},
            {"id": "demo-player-002", "name": "Comandante Sur",   "email": "sur@cloudrisk.app",   "password": "demo1234", "gold": 500},
            {"id": "demo-player-003", "name": "Comandante Este",  "email": "este@cloudrisk.app",  "password": "demo1234", "gold": 500},
            {"id": "demo-player-004", "name": "Comandante Oeste", "email": "oeste@cloudrisk.app", "password": "demo1234", "gold": 500},
        ]
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        db = firestore.Client(project=os.environ.get("PROJECT_ID", "cloudrisk-local"))
        col = settings.FIRESTORE_COLLECTION_USERS
        created = 0
        for p in DEMO_PLAYERS:
            doc_ref = db.collection(col).document(p["id"])
            if doc_ref.get().exists:
                continue
            doc_ref.set({
                "id": p["id"],
                "name": p["name"],
                "email": p["email"],
                "hashed_password": pwd_ctx.hash(p["password"]),
                "clan_id": None,
                "steps_total": 0,
                "power_points": 0,
                "gold": p["gold"],
                "level": 1,
                "created_at": datetime.utcnow().isoformat(),
            })
            created += 1
        print(f"[FIRESTORE] Seeded {created} demo players.")
    except Exception as e:
        print(f"[FIRESTORE] Player seeding skipped: {e}")


def _run_startup_seed() -> None:
    """Siembra las zonas de Valencia y los 4 jugadores demo al arrancar.

    En modo local todo va a `almacen_en_memoria`. En Firestore real (o
    emulador), delegamos en los dos helpers de seed específicos para que
    cada uno se pueda fallar de forma independiente.

    Después del seed, si la partida está 'cruda' (ninguna zona tiene owner)
    disparamos `ensure_game_setup()` — así el frontend se abre ya con las
    15×4 zonas repartidas y el pool de 30 armies por jugador, sin tener
    que hacer click manual en ningún botón. En prod el scheduler sigue
    siendo quien orquesta resets, pero para demo local es lo que menos
    fricción tiene.
    """
    if os.environ.get("USE_LOCAL_STORE", "0") == "1":
        from cloudrisk_api.database.almacen_en_memoria import seed_zones, seed_demo_players
        seed_zones()
        seed_demo_players()
    else:
        _seed_zones_firestore()
        _seed_demo_players_firestore()

    try:
        from cloudrisk_api.endpoints.turno import ensure_game_setup
        result = ensure_game_setup()
        if result:
            per_player = result.get("setup", {}).get("zones_per_player", {})
            free = result.get("setup", {}).get("free_zones_total", 0)
            print(f"[SETUP] Auto-setup done — zones per player: {per_player}, free: {free}")
    except Exception as e:
        print(f"[SETUP] Auto-setup skipped: {e}")


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            if event == "location_update":
                await zones.handle_location_update(
                    user_id=user_id, lat=data["lat"], lng=data["lng"], manager=manager,
                )
            elif event == "step_update":
                await steps.handle_step_update(
                    user_id=user_id, steps=data["steps"],
                )
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as exc:
        logger.warning(f"WebSocket error for {user_id}: {exc}")
        manager.disconnect(user_id)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "cloudrisk-api"}
