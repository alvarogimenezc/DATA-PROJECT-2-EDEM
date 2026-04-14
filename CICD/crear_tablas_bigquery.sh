#!/usr/bin/env bash
# Crea las tablas de BigQuery necesarias para el backend.
# Idempotente: si ya existen, no falla.
set -e

PROJECT_ID="${PROJECT_ID:-cloudrisk-492619}"
DATASET="${BQ_DATASET:-cloudrisk}"

echo "[setup_bq] Proyecto: $PROJECT_ID / dataset: $DATASET"

# Dataset (por si acaso)
bq --project_id="$PROJECT_ID" --location=EU mk -f "$DATASET" || true

# Tabla user_actions (histórico de acciones del backend)
bq --project_id="$PROJECT_ID" mk -f --table \
  "$PROJECT_ID:$DATASET.user_actions" \
  action_id:STRING,player_id:STRING,ts:TIMESTAMP,action_type:STRING,location_id:STRING,armies:INT64

echo "[setup_bq] Listo."
