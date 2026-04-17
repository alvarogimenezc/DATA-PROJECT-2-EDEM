#!/usr/bin/env bash
# seed_emulators.sh — Create Pub/Sub topics required by CloudRISK on the local emulator.
#
# The Firestore emulator auto-creates collections on first write, so only Pub/Sub
# needs explicit topic creation. Safe to run multiple times (ignores "already exists").
#
# Requires: docker compose stack up (pubsub-emulator healthy) and curl installed.

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
