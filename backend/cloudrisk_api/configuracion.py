"""
CloudRISK — Configuration
Pydantic-driven env var config for the backend. Reads from `.env` in
local dev and from Cloud Run env vars in prod (via --set-env-vars and
--set-secrets).

EDEM. Master Big Data & Cloud 2025/2026
Professor: Javi Briones & Adriana Campos
"""

import os
import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Game constants (not env-configurable — part of the game rules) ──────
MAX_ZONE_DEFENSE: int = 40         # cap on a zone's armies/defense_level
POWER_PER_STEPS_DEFAULT: int = 100 # steps needed to gain 1 power point


class Settings(BaseSettings):
    PROJECT_ID: str = "cloudrisk-local"

    # Pub/Sub topics — defaults align with the team contract in
    # alvarogimenezc/DATA-PROJECT-2-EDEM (air-quality, weather, player-movements).
    # The STEPS topic is the one Fran's walker, Álvaro's random_tracker fetcher,
    # and the backend /steps/sync endpoint all publish to. Keeping a single
    # topic means Noelia+Martha's Dataflow pipeline is the single consumer and
    # routes everything into BigQuery + Firestore.
    PUBSUB_TOPIC_LOCATION: str = "cloudrisk-location-events"
    PUBSUB_TOPIC_STEPS: str = "player-movements"
    PUBSUB_TOPIC_BATTLES: str = "cloudrisk-battle-events"

    # Firestore collections
    FIRESTORE_COLLECTION_USERS: str = "users"
    FIRESTORE_COLLECTION_CLANS: str = "clans"
    FIRESTORE_COLLECTION_ZONES: str = "zones"
    FIRESTORE_COLLECTION_BATTLES: str = "battles"
    FIRESTORE_COLLECTION_STEP_LOGS: str = "step_logs"

    # BigQuery
    BIGQUERY_DATASET: str = "cloudrisk_metrics"
    BIGQUERY_TABLE_USERS: str = "user_metrics"
    BIGQUERY_TABLE_BATTLES: str = "battle_metrics"
    BIGQUERY_TABLE_ZONES: str = "zone_metrics"

    # Auth — override via SECRET_KEY env var or .env file in production
    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    # Admin endpoints protection — Cloud Scheduler sends this token in X-Scheduler-Token header
    SCHEDULER_SECRET: str = "change-me-in-production"

    # Game config (CloudRISK v2 — "Walking Risk")
    CLOUDRISK_MIN_MEMBERS: int = 3
    BATTLE_DURATION_HOURS: int = 2
    # Ratio pasos/army — 500 pasos = 1 army. Diseñado para que un día
    # normal (10k pasos) te de ~20 armies, y un día "malo" (3k) te de 6.
    POWER_PER_STEPS: int = 500
    # Pool inicial en setup. v3.1 sube a 30 para que el jugador tenga
    # suficientes tropas que repartir entre zonas visibles y reclamar
    # alguna zona libre (15 zonas × 2 + 30 pool = 60 armies iniciales).
    STARTING_ARMIES_POOL: int = 30
    # Armies colocados automáticamente en cada zona al hacer el setup.
    # Con 2, cada zona puede atacar (necesita armies > dice) y la visualización
    # se ve "viva" (no todos los números en 1 apilados en el mapa).
    INITIAL_ARMIES_PER_ZONE: int = 2
    # Armies mínimas que recibes cada turno aunque tengas 0 zonas
    # (evita que un jugador casi eliminado no pueda hacer nada).
    MIN_TURN_BONUS: int = 3
    # Un "army" cada X zonas poseídas (Risk oficial usa 3).
    ZONES_PER_BONUS_ARMY: int = 3

    # Pydantic v2 style (was 'class Config: env_file = ...' in v1, deprecated).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Warn loudly if running with insecure defaults outside local mode
if os.environ.get("USE_LOCAL_STORE", "0") != "1":
    if settings.SECRET_KEY == "dev-secret-key":
        warnings.warn(
            "SECURITY: SECRET_KEY is set to the default dev value. "
            "Set the SECRET_KEY environment variable before deploying to production.",
            stacklevel=1,
        )
    if settings.SCHEDULER_SECRET == "change-me-in-production":
        warnings.warn(
            "SECURITY: SCHEDULER_SECRET is set to the default value. "
            "Set SCHEDULER_SECRET in Cloud Run env vars and Cloud Scheduler HTTP headers.",
            stacklevel=1,
        )
