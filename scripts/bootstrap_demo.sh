#!/usr/bin/env bash
# bootstrap_demo.sh — wrapper para macOS / Linux / WSL / Git Bash.
# Windows nativo: usa bootstrap_demo.ps1.
#
# Delega todo el trabajo en sembrar_demo.py (cross-platform).
# Este script solo:
#   1. Verifica que tienes Python 3 + gcloud.
#   2. Detecta el $PROJECT_ID si no lo pasas.
#   3. Instala dependencias mínimas si faltan.
#   4. Llama al .py con tus args.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { printf "  ${GREEN}✓${NC} %s\n" "$*"; }
info() { printf "  ${BLUE}→${NC} %s\n" "$*"; }
err()  { printf "  ${RED}✗${NC} %s\n" "$*" >&2; }

section() { printf "\n${BOLD}${BLUE}━━ %s ━━${NC}\n" "$*"; }

section "Pre-flight checks"

# 1. Python
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  err "Python 3 no encontrado. Instálalo: brew install python (macOS) o https://python.org"
  exit 1
fi
PYTHON_BIN="$(command -v python3 || command -v python)"
PYTHON_VERSION="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
ok "Python ${PYTHON_VERSION} en ${PYTHON_BIN}"

# 2. gcloud (solo si no estamos usando emuladores)
if [[ -z "${FIRESTORE_EMULATOR_HOST:-}" ]] && [[ -z "${PUBSUB_EMULATOR_HOST:-}" ]]; then
  if ! command -v gcloud >/dev/null 2>&1; then
    err "gcloud no encontrado. Instálalo: https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  ok "gcloud $(gcloud --version | head -1)"

  # ADC
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    err "Sin Application Default Credentials. Corre: gcloud auth application-default login"
    exit 1
  fi
  ok "Application Default Credentials presentes"
else
  info "Emulators en uso → saltando verificación gcloud"
fi

# 3. Project ID
PROJECT_ID="${PROJECT_ID:-${1:-}}"
if [[ -z "${PROJECT_ID}" ]] && command -v gcloud >/dev/null 2>&1; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
fi
if [[ -z "${PROJECT_ID}" ]]; then
  err "No se pudo determinar PROJECT_ID. Pásalo como 1er argumento o exporta PROJECT_ID=..."
  exit 1
fi
ok "Project: ${PROJECT_ID}"

# 4. Dependencias Python mínimas
section "Python deps"
if ! "${PYTHON_BIN}" -c 'import google.cloud.firestore, google.cloud.pubsub_v1, passlib' 2>/dev/null; then
  info "Instalando google-cloud-firestore + google-cloud-pubsub + passlib[bcrypt]..."
  "${PYTHON_BIN}" -m pip install --quiet --user \
    google-cloud-firestore \
    google-cloud-pubsub \
    'passlib[bcrypt]'
fi
ok "deps listas"

# 5. Launch
section "Launching sembrar_demo.py"
shift 2>/dev/null || true   # drop first arg if it was the project
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/sembrar_demo.py" --project "${PROJECT_ID}" "$@"
