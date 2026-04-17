# CloudRISK — Serverless Urban Conquest

> **Camina Valencia. Cada paso es munición. Conquista los 87 barrios.**
> Juego de estrategia geolocalizado tipo *Risk* sobre Valencia,
> construido como pipeline de datos **100 % serverless** en GCP.

![Python](https://img.shields.io/badge/python-3.12-blue)
![Node](https://img.shields.io/badge/node-20-brightgreen)
![GCP](https://img.shields.io/badge/cloud-GCP-4285F4)
![Terraform](https://img.shields.io/badge/iac-terraform-7B42BC)

**Máster Big Data & Cloud · EDEM 2025/2026 · Serverless Computing**

---

## Índice

1. [Qué es CloudRISK](#1-qué-es-cloudrisk)
2. [Arquitectura](#2-arquitectura)
3. [Parámetros del juego](#3-parámetros-del-juego)
4. [Arranque rápido en local](#4-arranque-rápido-en-local)
5. [Despliegue a GCP](#5-despliegue-a-gcp)
6. [Estructura del repo](#6-estructura-del-repo)
7. [Firestore — contrato de datos](#7-firestore--contrato-de-datos)
8. [Demo accounts + comandos útiles](#8-demo-accounts--comandos-útiles)
9. [Backup y restore de Firestore](#9-backup-y-restore-de-firestore)
10. [Runbook](#10-runbook)

---

## 1. Qué es CloudRISK

Los ejércitos y el oro de cada jugador **no se regalan**: salen de los pasos
que da en la vida real. Un pipeline streaming los valida (anti-trampa + caps),
los convierte en tropas y los escribe en Firestore; desde ahí el jugador los
despliega en el mapa.

Objetivo educativo: aplicar Pub/Sub, Dataflow stateful, Firestore, BigQuery,
Cloud Run y Terraform sobre un caso de uso real, sin un solo servidor encendido
permanentemente (salvo el job de Dataflow, que por diseño mantiene estado).

---

## 2. Arquitectura

```
Walker (Cloud Run Job, sintético)          ─► Pub/Sub: player-movements ─┐
Steps fetcher (Cloud Run Job, tracker)     ─► Pub/Sub: player-movements ─┤
Air ingestor (Cloud Run Service)           ─► Pub/Sub: air-quality      ─┤
Weather ingestor (Cloud Run Service)       ─► Pub/Sub: weather          ─┘
                                                         │
                             pipelines/cloudrisk_unified.py  (Dataflow streaming)
                             StatefulScoringDoFn por player_id:
                               · speed > 15 km/h   → DLQ anti-trampa
                               · cap pasos diario  (30 000)
                               · cap armies diario (50)
                               · multiplicador ambiental (aire × clima)
                               · timer 24 h resetea contadores
                                         │
                ┌────────────────────────┼─────────────────────────┐
                ▼                        ▼                         ▼
          Firestore                  BigQuery                BigQuery (DLQ)
          user_balance/         player_scoring_events         dead_letter
          users/                environmental_factors
                ▲                        ▲
                │                        │
                └────  Backend FastAPI (Cloud Run)  ──────────────┐
                       + /api/v1/analytics/* sobre BigQuery      │
                                                                  ▼
                                          Frontend React + MapLibre (Cloud Run)
                                          /game (mapa) + /analytics (gráficos)
```

| Componente | Servicio GCP | Escala a cero |
|---|---|:---:|
| Walker (bot sintético) | Cloud Run Job | sí |
| Steps fetcher (tracker GitHub) | Cloud Run Job | sí |
| Ingestores (air, weather) | Cloud Run Service | no (`min-instances=1`) |
| Backend FastAPI + /analytics | Cloud Run Service | sí |
| Frontend React | Cloud Run Service | sí |
| BD operativa | Firestore Native | — |
| Histórico analítico | BigQuery | — |
| Eventos | Pub/Sub | — |
| Scoring streaming | Dataflow (Flex Template) | no (1 worker min) |
| Secretos | Secret Manager | — |

---

## 3. Parámetros del juego

Definidos en `backend/cloudrisk_api/configuracion.py` y leídos por el pipeline
como env var / flag CLI (pasados por Terraform al Flex Template):

| Var | Default | Efecto |
|---|---|---|
| `POWER_PER_STEPS` | 500 | Pasos para 1 army |
| `DAILY_ARMY_CAP` | 50 | Tope armies/día por jugador |
| `DAILY_STEPS_CAP` | 30 000 | Tope pasos contables/día (anti-trampa) |
| `MAX_SPEED_KMH` | 15 | Umbral velocidad (> 15 → DLQ) |
| `MIN_GARRISON` | 2 | Invariante: toda zona con owner mantiene ≥ 2 armies |
| `BATTLE_DURATION_HOURS` | 2 | Ventana abierta de una batalla antes de resolverse |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 10 080 (7 d) | TTL del JWT |
| `SCHEDULER_SECRET` | (Secret Manager) | Token header `X-Scheduler-Token` para endpoints internos |

---

## 4. Arranque rápido en local

### Requisitos

- Python 3.12 (**no 3.13** — Apache Beam no lo soporta)
- Node 20
- Docker Desktop (opcional pero recomendado)
- `gcloud` CLI para el deploy

### Opción A — Docker Compose (un comando, todo arriba)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend (incl. `/analytics`) → http://localhost:3000
- API + Swagger → http://localhost:8080/api/v1/docs
- Firestore emulator → localhost:8200
- Pub/Sub emulator → localhost:8085

### Opción B — Sin Docker (3 terminales)

```bash
# Terminal 1 — Backend con store en memoria
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
USE_LOCAL_STORE=1 SECRET_KEY=dev python -m uvicorn cloudrisk_api.main:app --port 8080
```

```bash
# Terminal 2 — Frontend
cd frontend
npm ci
npm run dev  # http://localhost:3000
```

```bash
# Terminal 3 — Simulador de partida (opcional)
python data_generator/bot_ia_riesgo.py --interval 5
```

En modo `USE_LOCAL_STORE=1` el backend siembra automáticamente las 87 zonas de
Valencia y los 4 jugadores demo al arrancar — no necesitas GCP ni emuladores.

---

## 5. Despliegue a GCP

Infra declarativa con Terraform. Cuatro pasos totales.

### 5.1 — Preparar la máquina (una vez)

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project cloudrisk-492619
```

### 5.2 — Bucket para el state de Terraform (una vez)

```bash
gsutil mb -l europe-west1 gs://cloudrisk-492619-tfstate
gsutil versioning set on gs://cloudrisk-492619-tfstate
```

### 5.3 — Rellenar `terraform.tfvars`

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars

# Generar secretos fuertes (cross-platform)
python -c "import secrets; print('jwt_secret =', repr(secrets.token_hex(32)))"
python -c "import secrets; print('scheduler_secret =', repr(secrets.token_hex(32)))"
# Pega ambos en terraform.tfvars
```

### 5.4 — `terraform apply`

```bash
terraform init
terraform plan
terraform apply
```

Esto crea:

| Recurso | Cantidad | Archivo |
|---|:---:|---|
| APIs GCP habilitadas | 11 | `01_apis.tf` |
| Topics + subs Pub/Sub | 3 | `02_pubsub.tf` |
| Firestore Native (delete-protection + PITR) | 1 | `03_firestore.tf` |
| Dataset `cloudrisk` + 3 tablas (`player_scoring_events`, `environmental_factors`, `dead_letter`) | 1/3 | `04_bigquery.tf` |
| Repo Docker `cloudrisk` | 1 | `05_artifact_registry.tf` |
| Secrets (`cloudrisk-jwt-secret`, `openweather-api-key`, `scheduler-secret`) | 3 | `06_secrets.tf` |
| Service Accounts (backend, walker, ingestores, dataflow, scheduler) | 5 | `07_iam.tf` |
| Cloud Run Services (api, web, air, weather) + Job walker | 5 | `08_cloud_run.tf` |
| Cloud Scheduler crons (decay + resolve-expired) | 2 | `09_scheduler.tf` |
| Job fetcher del tracker + Scheduler diario | 1 + 1 | `11_steps_ingestor.tf` |
| Dataflow Flex Template + streaming Job (`cloudrisk_unified`) | 1 | `12_dataflow.tf` |

Tras el apply, `10_demo_seed.tf` corre automáticamente `scripts/sembrar_demo.py`
para dejar Firestore con 4 jugadores, 87 zonas (38 conquistadas) y 3 batallas
históricas. Para desactivarlo: `-var='seed_demo_on_apply=false'`.

### 5.5 — Inyectar la API key de OpenWeatherMap

Terraform crea el contenedor del secreto vacío; el valor lo metes aparte:

```bash
echo -n "TU_API_KEY_DE_OWM" \
  | gcloud secrets versions add openweather-api-key --data-file=-
```

### 5.6 — Construir las imágenes Docker

No usamos Cloud Build: cada servicio se compila y sube con `gcloud builds submit` directamente.

```bash
# Una imagen a la vez — patrón directo sin CICD wrapper
REGION=europe-west1
PROJECT=cloudrisk-492619
REPO=europe-west1-docker.pkg.dev/$PROJECT/cloudrisk

for svc in backend frontend weather_airq steps_ingestor data_generator; do
  gcloud builds submit $svc/ \
    --tag $REPO/$svc:latest \
    --region $REGION
done
```

Después, `terraform apply` otra vez (o `gcloud run deploy/jobs update`) para
que los Cloud Run apunten a las imágenes nuevas.

### 5.7 — Verificar

```bash
terraform output                              # URLs de cada servicio
curl "$(terraform output -raw api_url)/health"
```

Abre la URL del frontend y loguea con `este@cloudrisk.app / demo1234` — el
líder demo con 12 zonas.

---

## 6. Estructura del repo

```
backend/              FastAPI + router /api/v1/{users,zones,armies,battles,turn,analytics,...}
frontend/             React + Vite + MapLibre. /game (mapa) y /analytics (BQ).
pipelines/            cloudrisk_unified.py — pipeline Dataflow stateful (fan-in 3 topics).
steps_ingestor/       Cloud Run Job que pulla GitHub random_tracker → Pub/Sub.
weather_airq/         Ingestores clima + calidad de aire → Pub/Sub.
data_generator/       Walker sintético + bots de IA para demos.
consumer/             Debug consumer de Pub/Sub — NO desplegado, se puede borrar.
scripts/              sembrar_demo.py (seed Firestore) + wrappers bash/PowerShell.
data/                 Seeds estáticos JSON (players, zonas, mock_tracker_feed).
infrastructure/
  └─ terraform/       15 archivos .tf numerados por orden de dependencia.
docker-compose.yml    Stack local: API + frontend + emuladores Firestore/Pub/Sub.
.env.example          Variables documentadas (copiar a .env).
```

Detalle de cada subdirectorio en su propio `README.md`.

---

## 7. Firestore — contrato de datos

### Colecciones operativas (escribe el pipeline Dataflow)

```
user_balance/{player_id}
├── armies         int    # tropas disponibles
├── gold           int
├── total_steps    int    # acumulado desde el registro
├── steps_today    int    # acumulado del día (reset 24 h via timer Beam)
└── updated_at     str    # ISO timestamp

users/{player_id}
├── email          str
├── level          int
├── power_points   int
├── clan_color     str
└── last_scored_at str
```

### Colecciones del juego (escribe el backend)

```
zones/{zone_id}             Geojson, owner_clan_id, defense_level, conquered_at
clans/{clan_id}             Miembros, color, total_power (legacy)
battles/{battle_id}         Histórico de combates
step_logs/{log_id}          Auditoría append-only de sync de pasos
```

### Topics Pub/Sub

```
player-movements    {player_id, timestamp, latitude, longitude, steps_delta, speed_mps, source}
air-quality         {ts, ciudad, aqi, indice_multiplicador_aire, components, source}
weather             {ts, ciudad, temp_c, weather_main, indice_multiplicador_tiempo, source}
```

### Tablas BigQuery (dataset `cloudrisk`)

```
player_scoring_events  — 1 fila por evento procesado (player_id, ts, lat, lon,
                         steps_delta, speed_kmh, env_multiplier, armies_earned,
                         armies_today_after, capped, rejected, processed_at).
environmental_factors  — snapshots de aire + clima (histórico del multiplicador).
dead_letter            — eventos rechazados (JSON malo, anti-trampa).
```

---

## 8. Demo accounts + comandos útiles

### 4 comandantes pre-seedeados

| Email | Password | Facción |
|---|---|---|
| `norte@cloudrisk.app` | `demo1234` | Norte |
| `sur@cloudrisk.app` | `demo1234` | Sur |
| `este@cloudrisk.app` | `demo1234` | Este — líder (12 zonas) |
| `oeste@cloudrisk.app` | `demo1234` | Oeste |

Auto-login por defecto: Norte. Override: `?player=sur|este|oeste`.

### Comandos

| Qué | Comando |
|---|---|
| Tests backend | `cd backend && USE_LOCAL_STORE=1 SECRET_KEY=dev python -m pytest -v` |
| Build frontend | `cd frontend && npm run build` |
| Simular partida | `python data_generator/simulacion_multijugador.py --runs 3` |
| Sembrar Firestore (contra real o emulador) | `python scripts/sembrar_demo.py --project <ID>` |
| Verificar seed | `python scripts/sembrar_demo.py --project <ID> --dry-run` |
| Pipeline local | `python pipelines/cloudrisk_unified.py --runner=DirectRunner ...` (ver `pipelines/README.md`) |
| Disparar fetcher manualmente | `gcloud run jobs execute cloudrisk-steps-fetcher --region europe-west1 --wait` |
| Inspeccionar BQ | `bq query --use_legacy_sql=false "SELECT ... FROM cloudrisk.player_scoring_events ..."` |

---

## 9. Backup y restore de Firestore

Firestore NO tiene backup automático en free tier. Tres capas:

1. **Delete protection** — activada por Terraform en `03_firestore.tf`. Un `firestore databases delete` falla con mensaje claro.
2. **Point-in-Time Recovery (7 días)** — activada por Terraform. Restore a cualquier instante del último rolling:
   ```bash
   gcloud firestore databases restore \
     --source-backup=RESTORE_POINT \
     --destination-database=cloudrisk-recovered
   ```
3. **Export manual a GCS** (snapshot congelado):
   ```bash
   gsutil mb -l europe-west1 gs://cloudrisk-492619-backups
   gcloud firestore export gs://cloudrisk-492619-backups/firestore-$(date +%Y%m%d-%H%M%S)
   # Restore: gcloud firestore import gs://cloudrisk-492619-backups/<folder>
   ```

---

## 10. Runbook

| Síntoma | Causa probable | Fix |
|---|---|---|
| Backend 401 en `/users/me` | JWT vencido | Re-login, invalida token local |
| Frontend pantalla negra | Error JS en runtime | F12 → Console |
| `/turn/setup` devuelve 403 en prod | Falta `X-Scheduler-Token` | Lo inyecta Scheduler; en local usar `USE_LOCAL_STORE=1` |
| `/zones/{id}/attack` devuelve 400 "not adjacent" | Zonas no comparten frontera | Comprueba `GET /zones/adjacency` |
| Walker no publica | SA sin `roles/pubsub.publisher` | `terraform apply` (re-aplica IAM) |
| Dataflow no procesa | Worker SA sin acceso a Firestore | IAM `roles/datastore.user` en `07_iam.tf` |
| Eventos en `dead_letter` | Speed > 15 km/h o JSON mal formado | Revisa el productor, no el pipeline |
| Firestore queries lentas | Índice compuesto faltante | Consola Firestore → Indexes → Create |
| `terraform apply` bloqueado | Lock en state | `terraform force-unlock <LOCK_ID>` |

Para destruir todo (borra TU proyecto GCP):

```bash
gcloud firestore databases update --database='(default)' --delete-protection-state=DELETE_PROTECTION_DISABLED
cd infrastructure/terraform && terraform destroy
```

---

## Licencia

Proyecto educativo · EDEM 2025/2026 · Uso académico.
