#!/bin/bash
# CloudRISK — GCP Deploy Script
# Usage: ./deploy.sh <project-id> [region]
#
# Required env vars:
#   JWT_SECRET   — JWT signing secret for the API

set -euo pipefail

PROJECT_ID="${1:?Usage: deploy.sh <project-id> [region]}"
REGION="${2:-europe-west1}"
REPO="cloudrisk-images"                         # team contract name
STATE_BUCKET="${PROJECT_ID}-terraform-state"     # per-project to avoid clashes

: "${JWT_SECRET:?Set JWT_SECRET env var}"

echo "=================================="
echo "  CloudRISK — Deploying to GCP"
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "=================================="

# ─── 0. Authenticate & set project ───────────────────────────────────────────
gcloud config set project "$PROJECT_ID"

# ─── 1. Enable required APIs ─────────────────────────────────────────────────
echo "[1/6] Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com

# ─── 2. Create Artifact Registry repo ────────────────────────────────────────
echo "[2/6] Creating Artifact Registry..."
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="CloudRISK Docker images" \
  --quiet 2>/dev/null || echo "  (already exists)"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ─── 3. Terraform — provision infrastructure ─────────────────────────────────
echo "[3/6] Provisioning infrastructure with Terraform..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/terraform"

# Create GCS bucket for Terraform state (first time only)
gsutil mb -l "$REGION" "gs://${STATE_BUCKET}" 2>/dev/null || true
gsutil versioning set on "gs://${STATE_BUCKET}"

terraform init \
  -backend-config="bucket=${STATE_BUCKET}"

terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="jwt_secret=${JWT_SECRET}" \
  -auto-approve

cd - > /dev/null

# ─── 4. Build & push Docker images ───────────────────────────────────────────
echo "[4/6] Building and pushing Docker images..."
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
CODE_DIR="${SCRIPT_DIR}/.."                     # flattened: repo root is one level up

# API (la analítica está integrada aquí vía endpoints /analytics/*)
docker build -t "${REGISTRY}/api:latest" "${CODE_DIR}/backend"
docker push "${REGISTRY}/api:latest"

# ─── 5. Deploy API first ─────────────────────────────────────────────────────
echo "[5/6] Deploying to Cloud Run..."

gcloud run deploy cloudrisk-api \
  --image="${REGISTRY}/api:latest" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=10 \
  --memory=512Mi \
  --service-account="cloudrisk-api@${PROJECT_ID}.iam.gserviceaccount.com"

# Get real API URL (Cloud Run URLs are not guessable)
API_URL=$(gcloud run services describe cloudrisk-api \
  --region="$REGION" --format="value(status.url)")
echo "  API URL: $API_URL"

# Derive WebSocket URL from API URL (https → wss)
WS_URL=$(echo "$API_URL" | sed 's|^https|wss|')

# Build frontend with the real API and WebSocket URLs baked in
docker build \
  --build-arg "VITE_API_URL=${API_URL}" \
  --build-arg "VITE_WS_URL=${WS_URL}" \
  -t "${REGISTRY}/frontend:latest" \
  "${CODE_DIR}/frontend"
docker push "${REGISTRY}/frontend:latest"

gcloud run deploy cloudrisk-web \
  --image="${REGISTRY}/frontend:latest" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=5 \
  --memory=256Mi

# ─── 6. Print URLs ────────────────────────────────────────────────────────────
echo ""
echo "[6/6] Deploy complete!"
echo ""
echo "  API       : $(gcloud run services describe cloudrisk-api --region=$REGION --format='value(status.url)')"
echo "  Frontend  : $(gcloud run services describe cloudrisk-web --region=$REGION --format='value(status.url)')"
echo ""
echo "To set up CI/CD trigger:"
echo "  gcloud builds triggers create github \\"
echo "    --repo-name=<your-repo> \\"
echo "    --branch-pattern='^main$' \\"
echo "    --build-config=CICD/cloudbuild.yaml"
