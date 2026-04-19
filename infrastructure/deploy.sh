#!/bin/bash
# CloudRISK — Despliegue a GCP en 5 fases.
#
# Cada fase es un comando independiente. Si una falla, arreglas y reejecutas
# esa fase — las anteriores son idempotentes. No hay "one-liner mágico"
# porque el despliegue tiene dependencias reales (registry antes de imágenes,
# imágenes antes de Cloud Run, etc.).
#
# Uso:
#   bash infrastructure/deploy.sh <fase> <project-id> [region]
#
# Fases (en orden):
#   1 bootstrap  — habilita APIs + crea bucket de tfstate + terraform init
#   2 base       — terraform apply parcial: registry + secretos + bucket dataflow
#   3 images     — build & push de las 6 imágenes Docker
#   4 flex       — build del Dataflow flex template
#   5 apply      — terraform apply completo (Cloud Run + Dataflow + Scheduler)
#
# Variables opcionales (se generan aleatorias si no vienen):
#   JWT_SECRET        firma tokens JWT del backend
#   SCHEDULER_SECRET  token compartido entre Cloud Scheduler y el backend

set -euo pipefail

PHASE="${1:?Uso: deploy.sh <fase> <project-id> [region]. Fases: bootstrap|base|images|flex|apply}"
PROJECT_ID="${2:?Uso: deploy.sh <fase> <project-id> [region]}"
REGION="${3:-europe-west1}"

REPO="cloudrisk"
STATE_BUCKET="${PROJECT_ID}-terraform-state"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
TF_DIR="${SCRIPT_DIR}/terraform"

JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
SCHEDULER_SECRET="${SCHEDULER_SECRET:-$(openssl rand -hex 32)}"

TF_VARS=(
  -var="project_id=${PROJECT_ID}"
  -var="region=${REGION}"
  -var="jwt_secret=${JWT_SECRET}"
  -var="scheduler_secret=${SCHEDULER_SECRET}"
)

# ─── Fase 1: bootstrap ────────────────────────────────────────────────────────
phase_bootstrap() {
  echo "=== FASE 1/5 — bootstrap ==="
  gcloud config set project "$PROJECT_ID"

  echo "[1] Habilitando APIs de GCP..."
  gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    pubsub.googleapis.com \
    bigquery.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    dataflow.googleapis.com \
    iam.googleapis.com \
    cloudscheduler.googleapis.com \
    eventarc.googleapis.com \
    logging.googleapis.com

  echo "[2] Creando bucket de state de Terraform (si no existe)..."
  gsutil mb -l "$REGION" "gs://${STATE_BUCKET}" 2>/dev/null || echo "    (ya existe)"
  gsutil versioning set on "gs://${STATE_BUCKET}"

  echo "[3] terraform init con backend remoto..."
  cd "$TF_DIR"
  terraform init -backend-config="bucket=${STATE_BUCKET}" -reconfigure

  echo ""
  echo "OK — Ahora corre: bash infrastructure/deploy.sh base ${PROJECT_ID}"
}

# ─── Fase 2: base (registry + secretos + bucket dataflow) ─────────────────────
# Creamos SOLO las cosas que necesitamos antes de pushear imágenes. Usamos
# `-target` para limitar el apply. Terraform avisará con un warning — es
# esperado y seguro.
phase_base() {
  echo "=== FASE 2/5 — base (registry + secretos) ==="
  cd "$TF_DIR"

  terraform apply "${TF_VARS[@]}" \
    -target=google_artifact_registry_repository.cloudrisk \
    -target=google_secret_manager_secret_version.jwt_secret_v1 \
    -target=google_secret_manager_secret_version.scheduler_secret_v1 \
    -target=google_secret_manager_secret_version.owm_api_key_placeholder \
    -target=google_storage_bucket.dataflow \
    -auto-approve

  echo "[4] Configurando Docker para el Artifact Registry..."
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  echo ""
  echo "OK — Ahora corre: bash infrastructure/deploy.sh images ${PROJECT_ID}"
}

# ─── Fase 3: build & push de las 6 imágenes ───────────────────────────────────
phase_images() {
  echo "=== FASE 3/5 — build & push de imágenes ==="

  echo "[api] backend/ → ${REGISTRY}/api:latest"
  docker build -t "${REGISTRY}/api:latest" "${REPO_ROOT}/backend"
  docker push "${REGISTRY}/api:latest"

  echo "[frontend] frontend/ → ${REGISTRY}/frontend:latest"
  docker build -t "${REGISTRY}/frontend:latest" "${REPO_ROOT}/frontend"
  docker push "${REGISTRY}/frontend:latest"

  echo "[air-ingestor] weather_airq/ (target=air) → ${REGISTRY}/air-ingestor:latest"
  docker build \
    -f "${REPO_ROOT}/weather_airq/dockerfile" \
    --target air \
    -t "${REGISTRY}/air-ingestor:latest" \
    "${REPO_ROOT}/weather_airq"
  docker push "${REGISTRY}/air-ingestor:latest"

  echo "[weather-ingestor] weather_airq/ (target=weather) → ${REGISTRY}/weather-ingestor:latest"
  docker build \
    -f "${REPO_ROOT}/weather_airq/dockerfile" \
    --target weather \
    -t "${REGISTRY}/weather-ingestor:latest" \
    "${REPO_ROOT}/weather_airq"
  docker push "${REGISTRY}/weather-ingestor:latest"

  echo "[walker] data_generator/ → ${REGISTRY}/walker:latest"
  docker build -t "${REGISTRY}/walker:latest" "${REPO_ROOT}/data_generator"
  docker push "${REGISTRY}/walker:latest"

  echo "[steps-ingestor] steps_ingestor/ → ${REGISTRY}/steps-ingestor:latest"
  docker build -t "${REGISTRY}/steps-ingestor:latest" "${REPO_ROOT}/steps_ingestor"
  docker push "${REGISTRY}/steps-ingestor:latest"

  echo ""
  echo "OK — Ahora corre: bash infrastructure/deploy.sh flex ${PROJECT_ID}"
}

# ─── Fase 4: Dataflow flex template ───────────────────────────────────────────
# Esto NO es una imagen normal. `gcloud dataflow flex-template build`:
#   1) Construye una imagen Docker con tu pipeline y sus deps
#   2) La pushea al Artifact Registry
#   3) Sube un manifiesto JSON al GCS bucket de dataflow
# Terraform luego usa ese manifiesto para lanzar el job (12_dataflow.tf).
phase_flex() {
  echo "=== FASE 4/5 — Dataflow flex template ==="

  gcloud dataflow flex-template build \
    "gs://${PROJECT_ID}-dataflow/templates/cloudrisk-unified.json" \
    --image-gcr-path "${REGISTRY}/dataflow-unified:latest" \
    --sdk-language=PYTHON \
    --flex-template-base-image=PYTHON3 \
    --py-path="${REPO_ROOT}/pipelines/" \
    --env "FLEX_TEMPLATE_PYTHON_PY_FILE=cloudrisk_unified.py" \
    --env "FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=requirements.txt"

  echo ""
  echo "OK — Ahora corre: bash infrastructure/deploy.sh apply ${PROJECT_ID}"
}

# ─── Fase 5: terraform apply completo ─────────────────────────────────────────
phase_apply() {
  echo "=== FASE 5/5 — terraform apply completo ==="
  cd "$TF_DIR"
  terraform apply "${TF_VARS[@]}" -auto-approve

  echo ""
  echo "=== Despliegue completo ==="
  terraform output
  echo ""
  echo "IMPORTANTE — sube la key real de OpenWeatherMap:"
  echo "  echo -n 'TU_KEY' | gcloud secrets versions add openweather-api-key --data-file=-"
  echo ""
  echo "Mientras no lo hagas, air-ingestor y weather-ingestor no leen datos reales."
}

case "$PHASE" in
  bootstrap) phase_bootstrap ;;
  base)      phase_base ;;
  images)    phase_images ;;
  flex)      phase_flex ;;
  apply)     phase_apply ;;
  *) echo "Fase desconocida: $PHASE. Usa: bootstrap|base|images|flex|apply"; exit 1 ;;
esac
