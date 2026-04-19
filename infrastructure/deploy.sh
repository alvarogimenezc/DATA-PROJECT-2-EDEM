#!/bin/bash
# CloudRISK — Bootstrap previo a Terraform.
#
# Terraform no puede crear su propio bucket de state (necesita uno antes de
# correr `terraform init`). Tampoco se auto-loguea en GCP ni configura Docker.
# Este script hace esas 4 cosas, que solo hay que hacer UNA vez por máquina:
#
#   1) gcloud auth login + application-default login
#   2) Crear el bucket GCS donde vive el tfstate (versioned)
#   3) Habilitar las 2 APIs mínimas que Terraform necesita SÍ O SÍ para arrancar
#   4) gcloud auth configure-docker — para que los null_resource de
#      13_docker_builds.tf puedan hacer `docker push` al Artifact Registry
#
# Cuando termine, sigue con:
#   cd infrastructure/terraform
#   terraform init
#   terraform plan
#   terraform apply
#
# Uso:
#   bash infrastructure/deploy.sh <project-id> [region]

set -euo pipefail

PROJECT_ID="${1:?Uso: deploy.sh <project-id> [region]}"
REGION="${2:-europe-west1}"
STATE_BUCKET="${PROJECT_ID}-tfstate"

echo "=== CloudRISK — bootstrap previo a Terraform ==="
echo "Proyecto:      ${PROJECT_ID}"
echo "Region:        ${REGION}"
echo "State bucket:  gs://${STATE_BUCKET}"
echo ""

# ─── 1) Login en GCP ─────────────────────────────────────────────────────────
# Si ya estás logueado, gcloud no vuelve a abrir el navegador.
echo "[1/4] gcloud auth login..."
gcloud auth login --brief
gcloud auth application-default login --brief
gcloud config set project "$PROJECT_ID"

# ─── 2) Bucket GCS para el tfstate ──────────────────────────────────────────
# Versioned para que cualquier cagada sea reversible. Si ya existe, no falla.
echo ""
echo "[2/4] Creando bucket de tfstate (si no existe)..."
if gsutil ls "gs://${STATE_BUCKET}" >/dev/null 2>&1; then
  echo "    (ya existe)"
else
  gsutil mb -l "$REGION" "gs://${STATE_BUCKET}"
fi
gsutil versioning set on "gs://${STATE_BUCKET}"

# ─── 3) Habilitar APIs mínimas para que Terraform pueda arrancar ────────────
# Terraform luego habilita el resto en 01_apis.tf, pero estas 2 las necesita
# ANTES del primer `apply` (Artifact Registry para el push de imágenes y
# Cloud Resource Manager para el flujo de IAM que usa el propio Terraform).
echo ""
echo "[3/4] Habilitando APIs mínimas..."
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudresourcemanager.googleapis.com

# ─── 4) Auth de Docker contra el Artifact Registry de la región ─────────────
# Lo necesitan los null_resource de 13_docker_builds.tf para hacer docker push.
echo ""
echo "[4/4] Configurando Docker auth contra Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo ""
echo "=== Bootstrap OK ==="
echo ""
echo "Siguiente paso — corre:"
echo "  cd infrastructure/terraform"
echo "  terraform init"
echo "  terraform plan"
echo "  terraform apply"
echo ""
echo "Y después, una sola vez, sube la key real de OpenWeatherMap:"
echo "  echo -n 'TU_KEY' | gcloud secrets versions add openweather-api-key --data-file=-"
