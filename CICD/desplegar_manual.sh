#!/usr/bin/env bash
# =============================================================
# Deploy de los servicios CloudRISK a Cloud Run.
# Requisitos:
#   - gcloud autenticado como owner/editor del proyecto
#   - APIs habilitadas: run, cloudbuild, artifactregistry
# Uso:
#   bash CICD/desplegar_manual.sh            # deploya todo
#   bash CICD/desplegar_manual.sh backend    # solo backend
#   bash CICD/desplegar_manual.sh walker
# =============================================================
set -e

PROJECT_ID="${PROJECT_ID:-cloudrisk-492619}"
REGION="${REGION:-europe-west1}"
REPO="${REPO:-cloudrisk-images}"
TARGET="${1:-all}"

echo "[deploy] proyecto=$PROJECT_ID región=$REGION repo=$REPO target=$TARGET"

# --- Repo de Artifact Registry (idempotente) ---
gcloud artifacts repositories describe "$REPO" \
  --project="$PROJECT_ID" --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" \
    --project="$PROJECT_ID" --location="$REGION" \
    --repository-format=docker \
    --description="CloudRISK container images"

IMAGE_PREFIX="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO"

deploy_backend() {
  echo "[deploy] === backend ==="
  gcloud builds submit ./backend \
    --project="$PROJECT_ID" \
    --tag="$IMAGE_PREFIX/backend:latest"
  gcloud run deploy backend \
    --project="$PROJECT_ID" --region="$REGION" \
    --image="$IMAGE_PREFIX/backend:latest" \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,BQ_DATASET=cloudrisk,BQ_USER_ACTIONS_TABLE=user_actions" \
    --port=8080
}

deploy_walker() {
  echo "[deploy] === walker (Cloud Run Job) ==="
  gcloud builds submit ./data_generator \
    --project="$PROJECT_ID" \
    --tag="$IMAGE_PREFIX/walker:latest"
  # Cloud Run Job (el walker es un proceso continuo, no HTTP)
  gcloud run jobs describe walker --project="$PROJECT_ID" --region="$REGION" >/dev/null 2>&1 \
    && ACTION=update || ACTION=create
  gcloud run jobs "$ACTION" walker \
    --project="$PROJECT_ID" --region="$REGION" \
    --image="$IMAGE_PREFIX/walker:latest" \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,TOPIC_ID=player-movements,PLAYER_ID=player_001" \
    --max-retries=1 --task-timeout=3600s
  echo "[deploy] Ejecuta manualmente: gcloud run jobs execute walker --region=$REGION"
}

case "$TARGET" in
  backend) deploy_backend ;;
  walker)  deploy_walker ;;
  all)     deploy_backend; deploy_walker ;;
  *) echo "target desconocido: $TARGET (usa: backend | walker | all)"; exit 1 ;;
esac

echo "[deploy] Listo."
