#!/usr/bin/env bash
# seed_emulators.sh — Crea los topics de Pub/Sub necesarios en el emulador local.
#
# Es seguro ejecutarlo varias veces (ignora si el topic ya existe).
# Requiere tener Docker Compose corriendo y curl instalado.

set -euo pipefail

PUBSUB_HOST="${PUBSUB_EMULATOR_HOST:-localhost:8085}"
PROJECT="${PROJECT_ID:-cloudrisk-local}"

topics=(
  "cloudrisk-location-events"
  "cloudrisk-step-events"
  "cloudrisk-battle-events"
)

echo "[seed] Creating Pub/Sub topics on ${PUBSUB_HOST} for project=${PROJECT}..."
for topic in "${topics[@]}"; do
  url="http://${PUBSUB_HOST}/v1/projects/${PROJECT}/topics/${topic}"
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${url}")
  case "${status}" in
    200|409) echo "  ok  ${topic} (HTTP ${status})" ;;
    *)       echo "  FAIL ${topic} (HTTP ${status})" ; exit 1 ;;
  esac
done
echo "[seed] Done."
