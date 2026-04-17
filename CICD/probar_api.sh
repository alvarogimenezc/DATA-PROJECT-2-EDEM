#!/usr/bin/env bash
# Curls de prueba contra el backend local.
# Uso: bash CICD/probar_api.sh [player_id] [location_id] [armies]
set -e

BASE="${BASE:-http://localhost:8080}"
API="$BASE/api/v1"
PLAYER="${1:-player_001}"
LOCATION="${2:-ruzafa}"
ARMIES="${3:-1}"

echo "== GET /health =="
curl -s "$BASE/health" | jq . || curl -s "$BASE/health"
echo

echo "== GET /api/v1/state/player/$PLAYER =="
curl -s "$API/state/player/$PLAYER" | jq . || curl -s "$API/state/player/$PLAYER"
echo

echo "== GET /api/v1/state/locations =="
curl -s "$API/state/locations" | jq . || curl -s "$API/state/locations"
echo

echo "== POST /api/v1/actions/place =="
curl -s -X POST "$API/actions/place" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER\",\"location_id\":\"$LOCATION\",\"armies\":$ARMIES}" \
  | jq . || true
echo

echo "Swagger UI: $API/docs"
