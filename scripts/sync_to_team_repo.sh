#!/usr/bin/env bash
# sync_to_team_repo.sh — Sincroniza nuestra parte del código con el repositorio general del equipo.
#
# Uso:
#   bash scripts/sync_to_team_repo.sh pipelines      # (Para Noelia y Martha)
#   bash scripts/sync_to_team_repo.sh backend        # (Para Fran)

set -euo pipefail

COMPONENT="${1:-}"
if [[ -z "$COMPONENT" ]]; then
  echo "usage: $0 <walker|backend|weather_airq|pipelines|frontend|infra>" >&2
  exit 64
fi

OUR_REPO="$(pwd)"
TEAM_REPO="${TEAM_REPO:-$OUR_REPO/../team-repo}"

if [[ ! -d "$TEAM_REPO/.git" ]]; then
  echo "team repo not found at $TEAM_REPO — clone it first:" >&2
  echo "  git clone https://github.com/alvarogimenezc/DATA-PROJECT-2-EDEM.git $TEAM_REPO" >&2
  exit 65
fi

case "$COMPONENT" in
  walker)
    SRC="data_generator/"   DST="data_generator/"
    BRANCH="feat/fran-walker"
    MSG="feat(data_generator): juego_caminante.py + bot_ia_riesgo.py + simulacion_rapida_juego.py"
    ;;
  backend)
    SRC="backend/"          DST="backend/"
    BRANCH="feat/fran-backend"
    MSG="feat(backend): FastAPI + team-compat aliases + multipliers + dice combat"
    ;;
  weather_airq)
    SRC="weather_airq/"     DST="weather_airq/"
    BRANCH="feat/alvaro-weather_airq-mock"
    MSG="feat(weather_airq): mock fallback + Dockerfile multi-stage"
    ;;
  pipelines)
    SRC="pipelines/"        DST="pipelines/"
    BRANCH="feat/noelia-martha-beam"
    MSG="feat(pipelines): Beam Pub/Sub -> BigQuery with dead-letter"
    ;;
  frontend)
    SRC="frontend/"         DST="frontend/"
    BRANCH="feat/ricardo-3d-frontend"
    MSG="feat(frontend): 3D map, turn banner, dice panel, per-player colours"
    ;;
  infra)
    SRC=""   # handled specially below
    DST=""
    BRANCH="feat/fran-infra"
    MSG="feat(infra): docker-compose, CI/CD, GCP_TUTORIAL, seed scripts"
    ;;
  *)
    echo "unknown component: $COMPONENT" >&2
    exit 64
    ;;
esac

echo "[sync] component=$COMPONENT  branch=$BRANCH  team_repo=$TEAM_REPO"

cd "$TEAM_REPO"
git fetch origin main --quiet
git checkout -B "$BRANCH" origin/main

if [[ "$COMPONENT" == "infra" ]]; then
  rsync -a --delete "$OUR_REPO/docker-compose.yml"   ./
  rsync -a --delete "$OUR_REPO/Makefile"             ./ 2>/dev/null || true
  rsync -a --delete "$OUR_REPO/scripts/"             ./scripts/
  rsync -a --delete "$OUR_REPO/CICD/"                ./CICD/ 2>/dev/null || true
  rsync -a --delete "$OUR_REPO/docs/"                ./docs/
else
  rsync -a --delete "$OUR_REPO/$SRC" "./$DST"
fi

git add -A
if git diff --cached --quiet; then
  echo "[sync] no changes for $COMPONENT — branch is already up to date"
  exit 0
fi

git commit -m "$MSG"
git push -u origin "$BRANCH"

echo
echo "[sync] done. Open the PR in GitHub:"
echo "       https://github.com/alvarogimenezc/DATA-PROJECT-2-EDEM/compare/main...$BRANCH"
