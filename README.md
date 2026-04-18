# CloudRISK — Serverless Urban Conquest

> **Camina Valencia. Cada paso es munición. Conquista los 87 barrios.**
> Proyecto 100 % **serverless** sobre Google Cloud Platform.

## Índice

1. [Qué es CloudRISK](#1-qué-es-cloudrisk)
2. [Arquitectura serverless](#2-arquitectura-serverless)
3. [Arranque rápido en local](#5-arranque-rápido-en-local)
4. [Despliegue a GCP paso a paso](#6-despliegue-a-gcp-paso-a-paso) ⭐
5. [Cómo recibimos datos en tiempo real (random_tracker + demo seed)](#7-cómo-recibimos-datos-en-tiempo-real-random_tracker--demo-seed) ⭐⭐
6. [Terraform: qué hace cada archivo](#8-terraform-qué-hace-cada-archivo)
7. [Firestore — esquema y contrato](#9-firestore--esquema-y-contrato)
8.  [Backup y restore de Firestore](#10-backup-y-restore-de-firestore)
9.  [Demo accounts + comandos de dev](#11-demo-accounts--comandos-de-dev)
10. [CI/CD con Cloud Build](#12-cicd-con-cloud-build)
11. [Fusión con el repo del equipo](#13-fusión-con-el-repo-del-equipo)
12. [Runbook de incidencias comunes](#14-runbook-de-incidencias-comunes)
13. [Checklist de entrega](#15-checklist-de-entrega)

---

## 1. Qué es CloudRISK

Juego de estrategia geolocalizado tipo *Risk* sobre los 87 barrios de Valencia,
construido como pipeline de datos **100 % serverless**:

```
Walker (Cloud Run Job)          ─► Pub/Sub: player-movements ─┐
Air ingestor (Cloud Run)        ─► Pub/Sub: air-quality      ─┤
Weather ingestor (Cloud Run)    ─► Pub/Sub: weather          ─┤
Steps fetcher (Cloud Run Job)   ─► Pub/Sub: player-movements ─┤
                                                                ▼
                     Dataflow: pipelines/cloudrisk_unified.py
                     (Apache Beam streaming, stateful DoFn)
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
              BigQuery (analytics)                  Firestore (operativo)
              player_scoring_events                 user_balance/, users/
              environmental_factors
              dead_letter (DLQ)                              ▲
                    ▲                                         │
                    └──────── Backend FastAPI (Cloud Run) ────┘
                                         ▲
                                         │
                              Frontend React + MapLibre 3D
                              + /analytics/* (mismo front)
```

> **Refactor 2026-04:** un único pipeline Dataflow *stateful* absorbe la lógica
> que antes vivía en `src/dataflow_pipeline/pipeline.py`, `pipelines/ambiental_a_bq.py`
> y `steps_ingestor/puntuador_horario.py`. El **dashboard Streamlit**
> (`cloudrisk-dashboard`) se retira; la analítica se expone como endpoints
> `/api/v1/analytics/*` en el backend y se pinta en la página `/analytics`
> del front React.

Ni un solo recurso "encendido" siempre. Todo escala a cero. Coste con 10 partidas/día: **< 3 €/mes**.

---

## 2. Arquitectura serverless

**Regla:** ni un solo recurso "encendido" siempre. Todo escala a cero y paga por uso.

| Componente | Servicio GCP | Escala a cero | Coste idle |
|---|---|:---:|:---:|
| Walker (bot de pasos) | Cloud Run **Job** | sí | 0 € |
| Steps fetcher (tracker GitHub) | Cloud Run **Job** | sí | 0 € |
| Ingestores (air, weather) | Cloud Run Service (`min-instances=1`) | no | ~1 €/mes cada uno |
| Backend FastAPI | Cloud Run Service | sí | 0 € |
| Frontend React (+ /analytics) | Cloud Run Service | sí | 0 € |
| BD operativa | **Firestore Native** | — | 0 € hasta 1 GB |
| Analytics | **BigQuery** | — | 0 € hasta 1 TB queries/mes |
| Eventos | **Pub/Sub** | — | 0 € hasta 10 GB/mes |
| Streaming | **Dataflow** (autoscale) | sí (0 workers) | 0 € sin mensajes |
| Secretos | **Secret Manager** | — | 0.06 $/versión/mes |
| Build | **Cloud Build** | sí | 0 € |
| Registry | **Artifact Registry** | — | 0 € hasta 0.5 GB |

**Por qué esto importa para el temario:**

- Pub/Sub → evento desacoplado productor/consumidor
- Cloud Run Service vs Job → stateless vs batch
- Dataflow → streaming processing sin gestionar cluster
- BigQuery → columnar analytics sin infra
- Firestore → NoSQL operativo con índices automáticos

---

## 3. Mapa a los 13 temas del curso

Este proyecto **aplica uno a uno los 13 temas** que imparte Javi Briones en
[`Serverless_EDEM_2026/GCP`](https://github.com/jabrio/Serverless_EDEM_2026/tree/main/GCP):

| # | Tema del curso | Servicio GCP | Dónde en CloudRISK |
|---|---|---|---|
| 1 | Pub/Sub | `pubsub.googleapis.com` | 3 topics: `player-movements`, `air-quality`, `weather` |
| 2 | Apache Beam + Dataflow | `dataflow.googleapis.com` | `pipelines/cloudrisk_unified.py` (stateful DoFn por player_id) |
| 3 | Cloud Run | `run.googleapis.com` | 4 services (api, web, air, weather) + 2 jobs (walker, steps-fetcher) |
| 4 | Cloud Functions | `cloudfunctions.googleapis.com` | documentado (no usado — explicamos por qué) |
| 5 | CI/CD (Cloud Build) | `cloudbuild.googleapis.com` | `CICD/cloudbuild.yaml` |
| 6 | Firestore | `firestore.googleapis.com` | 4 colecciones (contrato + extendido) |
| 7 | Cloud Storage | `storage.googleapis.com` | bucket staging Dataflow + tfstate |
| 8 | Secret Manager | `secretmanager.googleapis.com` | `cloudrisk-jwt-secret`, `openweather-api-key` |
| 9 | Artifact Registry | `artifactregistry.googleapis.com` | repo `cloudrisk` con 5 imágenes |
| 10 | Eventarc | `eventarc.googleapis.com` | documentado (no usado — explicamos por qué) |
| 11 | Terraform (homework) | — | `infrastructure/terraform/` (15 archivos, incl. `12_dataflow.tf` Flex Template) |
| 12 | Vision AI | `vision.googleapis.com` | ❌ no aplicable (sin imágenes de usuario) |
| 13 | Logging / Monitoring | `logging.googleapis.com` | Cloud Run + Dataflow logs centralizados |

El recorrido completo vive en [`notebooks/00_PROYECTO_COMPLETO.ipynb`](./notebooks/00_PROYECTO_COMPLETO.ipynb).

---

## 5. Arranque rápido en local

### Requisitos

- Python 3.12 (**no 3.13** — Apache Beam no lo soporta)
- Node 20
- Docker Desktop (opcional pero recomendado)
- `gcloud` CLI ([install](https://cloud.google.com/sdk/docs/install))

### Docker Compose (1 comando, todo arriba)

```bash
git clone https://github.com/RicardoEdreiraPenas/DTP2-SAFE.git
cd DTP2-SAFE
cp .env.example .env
docker compose up --build
```

- Frontend (incluye `/analytics`) → http://localhost:3000
- API docs → http://localhost:8080/api/v1/docs

## 6. Despliegue a GCP paso a paso

> **Este es el flujo que queremos dominar.** Combina la **metodología de Terraform
> de Apepo** (infra como código, `init / plan / apply`) con los **comandos `gcloud`
> directos de Javi Briones** (`artifacts / builds / run deploy`) para el deploy
> de imágenes. Cada paso explica **qué vas a teclear, qué vas a ver y por qué**.
>
> Se ejecuta una sola vez para levantar todo. Luego el CI/CD actualiza los
> servicios con cada `git push`. **No usamos `make`** — sólo Terraform + gcloud
> + scripts bash en `CICD/`.

### 6.1 — Prepara tu máquina (una sola vez)

#### 🎯 Haces esto
```bash
# Instala gcloud CLI si no lo tienes
curl https://sdk.cloud.google.com | bash && exec -l $SHELL

# Instala Terraform (>= 1.8)
# macOS:   brew install terraform
# Linux:   https://developer.hashicorp.com/terraform/install
# Windows: choco install terraform

# Login con tu cuenta Google
gcloud auth login                         # te abre el navegador para tu cuenta EDEM
gcloud auth application-default login     # credenciales para clientes (Python, Terraform)

# Apunta al proyecto del equipo
gcloud config set project cloudrisk-492619
```

#### 👀 Ves esto
```
You are now logged in as [francisco92varas@gmail.com].
Updated property [core/project].
```

#### 💡 Por qué
- `gcloud auth login` → identidad humana en el CLI (para comandos como `gcloud run deploy`).
- `gcloud auth application-default login` → escribe `~/.config/gcloud/application_default_credentials.json`, que los SDK de Python (`google-cloud-firestore`, `bigquery`) y **Terraform** leen automáticamente. Sin esto, los scripts de seed y `terraform apply` fallan con `DefaultCredentialsError`.
- Son **dos logins distintos** — una molestia del primer día, nunca más.

---

### 6.2 — Crea el bucket para el Terraform state (una sola vez)

#### 🎯 Haces esto
```bash
gsutil mb -l europe-west1 gs://cloudrisk-492619-tfstate
gsutil versioning set on gs://cloudrisk-492619-tfstate
```

#### 👀 Ves esto
```
Creating gs://cloudrisk-492619-tfstate/...
Enabling versioning for gs://cloudrisk-492619-tfstate/...
```

#### 💡 Por qué
- `gsutil mb` (**m**ake **b**ucket) → el **state** de Terraform es un JSON que describe qué recursos existen. Si vive en tu portátil y lo pierdes → Terraform "olvida" todo y duplica recursos en GCP (coste real). **En GCS es compartido entre todos los del equipo**.
- `versioning` → cada `terraform apply` crea una nueva versión del state. Si alguien rompe algo, revertimos al state de hace 1 minuto.
- **Se crea con `gsutil`, no con Terraform** — es el clásico problema del huevo y la gallina (Terraform no puede crear el bucket donde va a guardar su propio state).

---

### 6.3 — Rellena `terraform.tfvars`

#### 🎯 Haces esto
```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars

# Genera un jwt_secret fuerte (cross-platform, funciona en Windows también)
python -c "import secrets; print(secrets.token_hex(32))"
# -> e3f2a1c9...64 hex chars...b8d7

# Abre terraform.tfvars con tu editor y pega el secret
```

#### 👀 Ves esto

El archivo queda así (y **NO se sube a git**, está en `.gitignore`):

```hcl
project_id = "cloudrisk-492619"
region     = "europe-west1"
jwt_secret = "e3f2a1c9...b8d7"
```

#### 💡 Por qué
- Terraform sustituye `var.project_id`, `var.region`, `var.jwt_secret` en todos los `.tf`. Cambiar el proyecto = cambiar 1 línea.
- `jwt_secret` se inyecta en Secret Manager vía Terraform y el backend lo lee en arranque. Así **el secret real vive en GCP**, no en git ni en tu disco.
- Usamos `python -c "secrets.token_hex(32)"` en vez de `openssl rand` porque Windows no trae OpenSSL por defecto — Python sí.

---

### 6.4 — Terraform: crea TODA la infraestructura permanente

Éste es el **corazón "Apepo"** del deploy: infra como código.

#### 🎯 Haces esto
```bash
cd infrastructure/terraform

terraform init       # descarga los providers + conecta al backend GCS
terraform plan       # LEE lo que hay y simula lo que creará (NO toca nada)
terraform apply      # crea 40+ recursos en GCP (te pide "yes" antes)
```

#### 👀 Ves esto
```
terraform init
Initializing the backend...
Successfully configured the backend "gcs"!
Initializing provider plugins...
- Finding hashicorp/google versions matching "~> 5.0"...
Terraform has been successfully initialized!

terraform plan
Plan: 47 to add, 0 to change, 0 to destroy.

terraform apply
…
Apply complete! Resources: 47 added, 0 changed, 0 destroyed.

Outputs:
api_url           = "https://cloudrisk-api-abc123-ew.a.run.app"
web_url           = "https://cloudrisk-web-def456-ew.a.run.app"
dataflow_job_id   = "2026-04-17_cloudrisk-unified_abc"
```

**Qué acabas de crear:**

| Recurso | Cuántos | Archivo Terraform |
|---|---|---|
| APIs GCP habilitadas | 12 | `01_apis.tf` |
| Topics Pub/Sub (`player-movements`, `air-quality`, `weather`) | 3 | `02_pubsub.tf` |
| Firestore Native DB + delete-protection + PITR | 1 | `03_firestore.tf` |
| Dataset BQ `cloudrisk` + tablas (`player_scoring_events`, `environmental_factors`, `dead_letter`) | 1 dataset · 3 tablas | `04_bigquery.tf` |
| Artifact Registry Docker repo `cloudrisk` | 1 | `05_artifact_registry.tf` |
| Secrets (`cloudrisk-jwt-secret`, `scheduler-secret`, `openweather-api-key`) | 3 | `06_secrets.tf` |
| Service Accounts con roles mínimos | 5 | `07_iam.tf` |
| Cloud Run Services (api, web, air, weather) | 4 | `08_cloud_run.tf` |
| Cloud Run Jobs (walker, steps-fetcher) | 2 | `08_cloud_run.tf` + `11_steps_ingestor.tf` |
| Cloud Scheduler (decay, resolve-expired, daily fetch) | 3 | `09_scheduler.tf` + `11_…` |
| Dataflow Flex Template + streaming Job (`cloudrisk_unified`) | 1 | `12_dataflow.tf` |

#### 💡 Por qué
- **`terraform init`**: descarga el provider `hashicorp/google` (v5+) y conecta con el bucket GCS del §6.2. Ejecutado 1× por portátil.
- **`terraform plan`**: **nunca se salta**. Es el "preview" — muestra cada recurso que va a añadir/cambiar/destruir. Si ves `destroy` y no esperabas borrar nada, **para y mira** antes de `apply`.
- **`terraform apply`**: pide `yes` antes de tocar. Tarda ~5 min la primera vez (crea 47 recursos). Después, los `apply` siguientes sólo tocan lo que cambió.
- **Separación por `.tf`**: `01_apis.tf`, `02_pubsub.tf`… así en un squad de 5 personas cada uno edita su archivo sin conflictos de merge (estilo Apepo: `0.STRUCTURE`, `1.GITHUB`, `2.GCP_SETUP`).

---

### 6.5 — Inyecta el secreto de OpenWeatherMap

Terraform creó el **contenedor** del secreto vacío en §6.4. Ahora le metemos el valor:

#### 🎯 Haces esto
```bash
# Pide la API key gratis en https://openweathermap.org/api
echo -n "TU_API_KEY_DE_OWM" \
  | gcloud secrets versions add openweather-api-key --data-file=-
```

#### 👀 Ves esto
```
Created version [1] of the secret [openweather-api-key].
```

#### 💡 Por qué
- Queremos el secreto en **Secret Manager**, no en `terraform.tfvars` (que aunque esté en `.gitignore`, puede acabar en un screenshot o un log).
- `echo -n` → sin el `-n` añadirías un `\n` final que rompe la clave.
- `--data-file=-` → lee el valor de stdin. Si escribieras `--data-file=mi_clave.txt`, el archivo aparecería en tu `history` del shell. Stdin desaparece en cuanto cierras la terminal.

---

### 6.6 — Construye las imágenes Docker con Cloud Build

Éste es el **corazón "Javi Briones"** del deploy: `gcloud artifacts → builds submit → run deploy`.

Terraform no compila código — Cloud Build sí. Terraform creó los **contenedores vacíos** de Cloud Run apuntando a imágenes que todavía no existen; ahora las construimos.

#### 🎯 Haces esto (opción A: todo de una, con Cloud Build YAML)
```bash
# Desde la raíz del repo — compila 5 imágenes en paralelo
gcloud builds submit --config=CICD/cloudbuild.yaml .
```

#### 🎯 Haces esto (opción B: un servicio a la vez, Javi-style)
```bash
# Patrón del profesor Javi Briones — cada servicio por separado
bash CICD/desplegar_manual.sh backend           # FastAPI (+ /analytics/*)
bash CICD/desplegar_manual.sh walker            # Cloud Run Job (pasos sintéticos)
bash CICD/desplegar_manual.sh frontend          # React + Vite (+ /analytics)
bash CICD/desplegar_manual.sh steps-ingestor    # fetcher diario del tracker
```

El script `desplegar_manual.sh` es un wrapper fino de **exactamente los 3
comandos del profesor**:

```bash
# lo que el script hace por ti para cada servicio:
gcloud artifacts repositories create cloudrisk \
  --repository-format=docker --location=europe-west1
gcloud builds submit <carpeta>/ \
  --tag europe-west1-docker.pkg.dev/cloudrisk-492619/cloudrisk/<svc>:latest
gcloud run deploy cloudrisk-<svc> \
  --image europe-west1-docker.pkg.dev/cloudrisk-492619/cloudrisk/<svc>:latest \
  --region europe-west1 --platform managed --allow-unauthenticated
```

#### 👀 Ves esto
```
Creating temporary tarball archive of 42 file(s) totalling 180.5 KiB
Uploading tarball of [.] to gs://cloudrisk-492619_cloudbuild/source/...
BUILD SUCCESS
Service [cloudrisk-backend] revision [cloudrisk-backend-00001-abc] has been deployed
Service URL: https://cloudrisk-backend-xxxxx-ew.a.run.app
```

#### 💡 Por qué
- **Separación Terraform vs gcloud** = separación **infra vs imagen**. Terraform gestiona cosas que cambian poco (topics, tablas, IAM). `gcloud builds submit` gestiona lo que cambia con cada commit (la imagen Docker).
- **`gcloud artifacts repositories create`**: registro privado de imágenes Docker en Europe-west1. Sólo se crea 1 vez — si ya existe, el script salta (`describe || create`).
- **`gcloud builds submit --tag ...`**: sube tu carpeta (`backend/`) a GCS, lanza Cloud Build con el `Dockerfile` que hay dentro, y al terminar deja la imagen en Artifact Registry. Todo sin que tengas Docker instalado.
- **`gcloud run deploy … --allow-unauthenticated`**: crea/actualiza el servicio con una URL pública. Para endpoints internos del backend (`/turn/setup`, `/battles/resolve-expired`) usamos el header `X-Scheduler-Token` (ver `06_secrets.tf` → `scheduler-secret`) y Scheduler lo inyecta automáticamente.
- **Primera compilación**: ~8 min. Siguientes con cache: ~2 min.

---

### 6.7 — Lanza el pipeline Dataflow unificado

Streaming continuo: los 3 topics Pub/Sub → `cloudrisk_unified.py` (Beam stateful) → Firestore + BigQuery.

> Normalmente lo despliega Terraform (`12_dataflow.tf`, Flex Template). Este
> comando manual sirve para pruebas o si necesitas lanzar una versión parcheada
> fuera del ciclo de Terraform.

#### 🎯 Haces esto
```bash
# Crea el bucket staging (una vez)
gsutil mb -l europe-west1 gs://cloudrisk-492619-dataflow

# Lanza el job streaming — requiere Python 3.12 (NO 3.13)
python pipelines/cloudrisk_unified.py \
  --runner=DataflowRunner \
  --project=cloudrisk-492619 \
  --region=europe-west1 \
  --temp_location=gs://cloudrisk-492619-dataflow/tmp \
  --staging_location=gs://cloudrisk-492619-dataflow/staging \
  --player_sub=projects/cloudrisk-492619/subscriptions/player-movements-sub \
  --weather_sub=projects/cloudrisk-492619/subscriptions/weather-sub \
  --airq_sub=projects/cloudrisk-492619/subscriptions/air-quality-sub \
  --scoring_table=cloudrisk-492619:cloudrisk.player_scoring_events \
  --env_table=cloudrisk-492619:cloudrisk.environmental_factors \
  --dlq_table=cloudrisk-492619:cloudrisk.dead_letter \
  --streaming
```

#### 👀 Ves esto
```
INFO: Starting the Dataflow job 'cloudrisk-unified-…'
INFO: Created job with id: 2026-04-17_…
```

Ve a la consola: `https://console.cloud.google.com/dataflow/jobs?project=cloudrisk-492619`
y verás el DAG ejecutándose en tiempo real.

#### 💡 Por qué
- **`--runner=DataflowRunner`** → lo ejecuta GCP, no tu portátil. Autoescala workers según carga (0 si no hay mensajes).
- **`--streaming`** → el job no termina; se queda escuchando Pub/Sub indefinidamente.
- **Subscriptions `-sub`** → Terraform las creó en §6.4. Los nombres `player-movements-sub`, `weather-sub`, `air-quality-sub` son el **contrato del equipo**.
- **Stateful DoFn por `player_id`** → aplica anti-trampa (speed > 15 km/h → DLQ) + caps diarios (armies y pasos). Ver `pipelines/README.md`.

---

### 6.8 — Siembra datos de demo (partida lista para jugar)

#### 🎯 Haces esto
```bash
cd ../..   # vuelve a la raíz del repo

# macOS / Linux / WSL / Git Bash
bash CICD/sembrar_demo.sh cloudrisk-492619

# Windows PowerShell
.\scripts\bootstrap_demo.ps1 -Project cloudrisk-492619
```

#### 👀 Ves esto
```
▶ sembrar_demo.sh  project=cloudrisk-492619
✔ 4 users       (norte / sur / este / oeste @ cloudrisk.app, pass=demo1234)
✔ 86 zones      (barrios de Valencia)
✔ 4 user_balance docs  (contrato del equipo)
✔ 86 location_balance docs (38 conquistadas, 48 libres)
✔ 3 battles en histórico
✔ 4 mensajes a air-quality y weather
```

#### 💡 Por qué
- Los recursos están vacíos tras el apply — sin este paso, el frontend arranca en un mapa vacío sin jugadores.
- **Idempotente** (`merge=True`): puedes relanzar el script las veces que quieras. No duplica.
- Hay detalle completo en §7 (sección grande de datos en tiempo real).

---

### 6.9 — Verifica que todo funciona

#### 🎯 Haces esto
```bash
# URLs de tus servicios
cd infrastructure/terraform
terraform output

# Smoke test del API
curl "$(terraform output -raw api_url)/health"

# Cuenta docs en Firestore
bash ../../CICD/verificar_demo.sh cloudrisk-492619

# Abre el frontend
# macOS:
open "$(terraform output -raw web_url)"
# Windows PowerShell:
Start-Process (terraform output -raw web_url)
# Linux:
xdg-open "$(terraform output -raw web_url)"
```

#### 👀 Ves esto
```
$ curl .../health
{"status":"ok","service":"cloudrisk-api","version":"1.0.0"}

$ bash CICD/verificar_demo.sh cloudrisk-492619
Proyecto: cloudrisk-492619
  users                   4 docs   [OK]
  zones                  86 docs   [OK]
  user_balance            4 docs   [OK]
  location_balance       86 docs   [OK]
  battles                 3 docs   [OK]
```

Si el `/health` devuelve JSON y el `verificar_demo.sh` muestra `[OK]` en las 5 colecciones, **el deploy está completo**. Accede con `este@cloudrisk.app / demo1234` (líder demo con 12 zonas) y deberías ver el mapa con 38 zonas coloreadas.

#### 💡 Por qué
- `terraform output` lee del state en GCS y te devuelve todas las URLs sin pedirlas a GCP una por una.
- `/health` es un endpoint `@app.get` del FastAPI que sólo devuelve `{"status":"ok"}`. Si devuelve otro código HTTP → el pod arranca pero algo crashea en runtime.
- `verificar_demo.sh` golpea Firestore directo (sin pasar por el API) → aísla "el seed funciona" de "el API funciona".

---

## 7. Cómo recibimos datos en tiempo real (random_tracker + demo seed)

> **Éste es el corazón pedagógico del proyecto.** Un sistema serverless que todos los
> días recibe pasos reales de una fuente externa, los convierte en puntos del juego
> y los deja visibles al jugador en **< 1 hora** — sin un solo servidor encendido
> entre una ejecución y la siguiente.
>
> Esta sección explica **qué llega, de dónde, cómo, cada cuánto, quién lo procesa
> y dónde aterriza**. Si sólo vas a leer una sección, que sea ésta.

### 7.1 — El principio: pasos reales → puntos del juego

En CloudRISK, los **ejércitos y el oro** de cada jugador no se regalan: salen de
los pasos que da en la vida real. Esto obliga al sistema a tener una pipeline
de datos **continua** (no un job one-shot) que:

1. **Capte** pasos reales desde una fuente externa (`random_tracker`, repo GitHub).
2. **Los transporte** como eventos individuales (Pub/Sub).
3. **Los convierta en estado de juego en streaming** (Dataflow *stateful* por `player_id`):
   anti-trampa (> 15 km/h → DLQ), caps diarios de pasos/armies, multiplicador ambiental.
4. **Los persista**: estado hot en Firestore (`user_balance`, `users`) + histórico
   en BigQuery (`player_scoring_events`) para que `/analytics/*` pueda consultarlo.
5. **Sea observable** por el jugador desde el frontend (endpoint de estado en vivo).

> **Nota de arquitectura:** antes había un Cloud Run Service
> (`cloudrisk-hourly-scorer`) que leía BQ y escribía Firestore cada hora.
> Se retiró — toda esa lógica vive ahora en el `StatefulScoringDoFn` del
> pipeline Dataflow, por-evento y sin cron horario.

### 7.2 — Diagrama de la pipeline completa

```
┌──────────────────────────────────────────────────────────────────────────┐
│  FUENTE EXTERNA                                                          │
│  github.com/FranciscoAlvarezVaras/random_tracker/movements.json          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  (pull 1×/día, 03:00 Madrid)
                                  ▼
                  ┌───────────────────────────────────┐
                  │  Cloud Run JOB                    │
                  │  cloudrisk-steps-fetcher          │
                  │  (recolector_pasos_diario.py)     │
                  │                                   │
                  │  - resuelve player_id (mapping)   │
                  │  - marca idempotencia SHA256      │
                  │  - publica 1 msg por movimiento   │
                  └───────────────┬───────────────────┘
                                  │  JSON por mensaje:
                                  │  { player_id, ts, steps_delta,
                                  │    latitude, longitude, speed_mps,
                                  │    source:"real", ingested_at }
                                  ▼
           ┌──────────────────────────────────────────┐
           │  Pub/Sub Topic: player-movements         │  ◄─── también publica
           │  (bus único, multi-producer)             │       el walker y el
           └──────────────────┬───────────────────────┘       backend /steps/sync
                              │
                              ▼
           ┌────────────────────────────────────────────────┐
           │  Dataflow streaming (Apache Beam)              │
           │  pipelines/cloudrisk_unified.py                │
           │  StatefulScoringDoFn por player_id:            │
           │    · speed > 15 km/h → DLQ anti-trampa         │
           │    · cap pasos diario (30 000)                 │
           │    · armies = (pasos // 500) × mult ambiental  │
           │    · cap armies diario (50)                    │
           │    · timer 24 h → reset contadores             │
           └───────┬────────────────┬─────────────┬─────────┘
                   │                │             │
                   ▼                ▼             ▼
        ┌────────────────┐  ┌───────────────┐  ┌───────────────────┐
        │  Firestore     │  │  BigQuery     │  │  BigQuery (DLQ)   │
        │  user_balance/ │  │  player_      │  │  dead_letter      │
        │  (armies, gold,│  │  scoring_     │  │  (rechazados +    │
        │   last_scored) │  │  events       │  │   JSON malos)     │
        │  users/{id}    │  │  (histórico   │  └───────────────────┘
        │  (steps_total) │  │   por evento) │
        └────────┬───────┘  └───────┬───────┘
                 │                  │
                 │                  ▼
                 │       GET /api/v1/analytics/* (top-steps, top-rainy-days…)
                 │
                 ▼
      ┌──────────────────────────────┐
      │  Frontend React              │
      │  - /game: mapa MapLibre + HUD│
      │  - /analytics: gráficos BQ   │
      │  - GET /steps/realtime-      │
      │        ingestion-status      │
      └──────────────────────────────┘
```

### 7.3 — Cadencia y responsabilidad

| Cuándo | Quién lo dispara | Qué hace | Dónde aterriza |
|---|---|---|---|
| `03:00 Europe/Madrid` (diario) | `cloudrisk-steps-fetcher-daily` (Cloud Scheduler) | `Cloud Run Job` lee `random_tracker/movements.json`, publica N mensajes al topic | Pub/Sub `player-movements` |
| continuo (streaming, por-evento) | Dataflow worker (autoscale 0→N) con stateful DoFn | Anti-trampa + caps + scoring; escribe Firestore y BQ en el mismo pipeline | Firestore `user_balance`, `users` · BQ `player_scoring_events` · DLQ `dead_letter` |
| on-demand | Frontend (cada 30 s cuando el jugador abre el HUD) | `GET /steps/realtime-ingestion-status` | Respuesta JSON con desglose por `source` |
| on-demand | Frontend página `/analytics` | `GET /api/v1/analytics/{top-steps-month, top-rainy-days, top-bad-air, user/{id}/history}` | Gráficos recharts sobre histórico BQ |

### 7.4 — Por qué Pub/Sub como "bus único"

El topic `player-movements` recibe de **tres productores distintos** y se
distingue con el campo `source`:

| Productor | `source` | Propósito |
|---|---|---|
| `cloudrisk-steps-fetcher` (diario) | `"real"` | Pasos reales del GitHub `random_tracker` |
| `walker` (Cloud Run Job, simulador) | `"synthetic_walker"` | Partidas demo y tests E2E |
| Backend `POST /steps/sync` (app móvil) | `"backend_sync"` | Pasos que la app del usuario empuja manualmente |

**Ventaja:** la pipeline de Noelia+Martha es **una sola** — cambiar de fuente
no implica cambiar el pipeline, solo filtrar por `source` si hace falta.

### 7.5 — Idempotencia (cero duplicados aunque el Scheduler reintente)

`recolector_pasos_diario.py` calcula un `sha256` del JSON descargado y escribe
un marker en Firestore `step_ingests/{YYYY-MM-DD}`:

```python
{
  "date": "2026-04-16",
  "sha256": "abc123...",
  "count": 142,
  "ingested_at": "2026-04-16T03:00:12Z"
}
```

Si el Scheduler reintenta (hiccup de red, timeout, etc.) la segunda ejecución
ve el marker con el mismo `sha256` → **aborta sin publicar nada**. Nunca se
duplican pasos, nunca se duplican puntos.

### 7.6 — Archivos involucrados (mapa de código)

| Archivo | Rol | Quién lo mantiene |
|---|---|---|
| `steps_ingestor/recolector_pasos_diario.py` | Cloud Run Job: tira `random_tracker` y publica | Álvaro |
| `steps_ingestor/Dockerfile` | Imagen del Cloud Run Job | Álvaro |
| `steps_ingestor/requirements.txt` | `google-cloud-{pubsub,firestore}` | Álvaro |
| `pipelines/cloudrisk_unified.py` | Job Dataflow unificado (stateful DoFn por jugador) | Noelia + Martha |
| `data/random_tracker_mapping.json` | Mapea usuario GitHub → `player_id` | Álvaro |
| `data/mock_tracker_feed.json` | Feed offline para dev/test sin red | Álvaro |
| `infrastructure/terraform/11_steps_ingestor.tf` | Cloud Run Job + Scheduler diario + IAM | Fran |
| `infrastructure/terraform/12_dataflow.tf` | Flex Template + job Dataflow del pipeline unificado | Fran |
| `backend/cloudrisk_api/endpoints/pasos.py` | Endpoint `GET /steps/realtime-ingestion-status` | Fran |
| `backend/cloudrisk_api/endpoints/analiticas.py` | Endpoints `/analytics/*` que consultan BQ | Fran |
| `backend/cloudrisk_api/database/publicador_pubsub.py` | Publica con `source="backend_sync"` | Fran |
| `notebooks/02_alvaro_ingestion.ipynb` §B | Guion paso-a-paso (celdas B.1–B.8) | Álvaro |

### 7.7 — Demo seed permanente (cross-platform Windows + macOS)

Cuando haces `terraform apply` por primera vez, **no queremos un entorno vacío**
— queremos que el juego esté arrancado con 4 comandantes, 87 zonas, 3 batallas
en curso y ~60 ejércitos ya repartidos. Para eso existe el "demo seed":

**Archivos:**

- `data/demo_game_state.json` — estado mid-game determinista (4 players, 38 zonas poseídas, 3 battles)
- `scripts/sembrar_demo.py` — orquestador Python (UTF-8 en Windows, bcrypt, merge=True idempotente)
- `scripts/bootstrap_demo.sh` — wrapper bash (Linux/macOS)
- `scripts/bootstrap_demo.ps1` — wrapper PowerShell (Windows)
- `CICD/sembrar_demo.sh` — wrapper del equipo, estilo Álvaro (`bash CICD/sembrar_demo.sh`)
- `CICD/verificar_demo.sh` — cuenta documentos en Firestore tras el seed
- `infrastructure/terraform/10_demo_seed.tf` — `null_resource` con `local-exec` que elige PS o sh según plataforma

#### 🎯 Haces esto (cómo lo usa el equipo)

```bash
# macOS / Linux / WSL / Git Bash — estilo equipo Álvaro
bash CICD/sembrar_demo.sh cloudrisk-492619

# Windows PowerShell — mismo resultado
.\scripts\bootstrap_demo.ps1 -Project cloudrisk-492619

# Cualquier plataforma — directo al Python
python scripts/sembrar_demo.py --project cloudrisk-492619
```

O **automáticamente** desde Terraform (se lanza después del `apply`):

```bash
cd infrastructure/terraform
terraform apply -var='seed_demo_on_apply=true'
```

#### 💡 Por qué
- Un `terraform apply` solo crea infra vacía. Sin el seed, el frontend arranca en un mapa completo de Valencia **sin ningún jugador** → parece que todo falló.
- Los tres wrappers (`.sh`, `.ps1`, `sembrar_demo.sh`) llaman todos al **mismo `sembrar_demo.py`**. Usa el que mejor encaje con tu terminal.
- `seed_demo_on_apply=true` es un flag Terraform que dispara un `null_resource` con `local-exec` — útil en CI/CD donde no hay humano para ejecutar comandos después del apply.

Al terminar verás algo como:

```
✔ 4 users seeded       (norte / sur / este / oeste — cardinales de Valencia)
✔ 86 zones seeded      (Valencia neighbourhoods)
✔ 4 user_balance docs  (armies + gold + steps + level listos)
✔ 86 location_balance docs   (38 conquistadas, 48 libres)
✔ 3 battles recientes en el histórico
✔ 4 mensajes de ejemplo publicados a air-quality / weather

Login demo (todos con pass demo1234):
  norte@cloudrisk.app   · 280 armies · 10 zonas · 640 gold · lvl 3
  sur@cloudrisk.app     · 220 armies ·  8 zonas · 480 gold · lvl 3
  este@cloudrisk.app    · 340 armies · 12 zonas · 820 gold · lvl 4   ← líder
  oeste@cloudrisk.app   · 190 armies ·  8 zonas · 360 gold · lvl 2
```

> **Tip para la demo en clase:** empieza logueado como `este@cloudrisk.app`
> (es el líder) desde tu máquina y abre otra ventana de incógnito con
> `norte@cloudrisk.app` — verás los dos mapas con zonas distintas y podrás
> enseñar un ataque en vivo entre barrios.

### 7.8 — Qué queda "encendido" tras el apply (y cuánto cuesta)

| Recurso | Estado idle | Coste idle |
|---|---|---|
| `cloudrisk-steps-fetcher` (Cloud Run Job) | escalado a 0 | 0 € |
| Dataflow `cloudrisk-unified` (streaming) | 1 worker mínimo (autoscale) | ~30-40 €/mes con tráfico demo (la pieza *no* escala a cero) |
| Cloud Scheduler (fetcher diario) | inactivo 23 h/día | < 0,10 €/mes |
| `player_scoring_events` + `dead_letter` (BigQuery) | ≈ 500 KB/día | < 0,01 €/mes en storage |
| Pub/Sub topics | sin retención prolongada | 0 € con volumen demo |

**Total esperado con partida demo 24/7: ~30-40 €/mes** — el coste lo carga
Dataflow, que por diseño **no escala a cero** (necesita al menos 1 worker
vivo para mantener el estado). El resto de servicios siguen a 0 € idle.

### 7.9 — Verificar la pipeline end-to-end (5 comandos)

#### 🎯 Haces esto (los 5 pasos, en orden)

```bash
# 1) Dispara el fetcher ahora mismo (sin esperar a las 03:00 Madrid)
gcloud run jobs execute cloudrisk-steps-fetcher --region europe-west1 --wait

# 2) Confirma que llegaron mensajes al topic
gcloud pubsub subscriptions pull player-movements-debug --auto-ack --limit 5

# 3) Verifica que aterrizaron en BigQuery (player_scoring_events)
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) AS events, COUNT(DISTINCT player_id) AS players
   FROM \`cloudrisk-492619.cloudrisk.player_scoring_events\`
   WHERE DATE(processed_at) = CURRENT_DATE()"

# 4) Comprueba la DLQ — si hay eventos aquí, revisa los logs de Dataflow
bq query --use_legacy_sql=false \
  "SELECT rejection_reason, COUNT(*) AS n
   FROM \`cloudrisk-492619.cloudrisk.dead_letter\`
   WHERE DATE(processed_at) = CURRENT_DATE()
   GROUP BY rejection_reason"

# 5) Mira cómo subieron los armies del jugador en Firestore
bash CICD/verificar_demo.sh cloudrisk-492619
```

#### 👀 Ves esto
```
1) Execution [cloudrisk-steps-fetcher-abc] has successfully completed.
2) ┌─────────────────────────────────────────────────────────────┐
   │ DATA                                                        │
   │ {"player_id":"alvaro","steps_delta":320,"source":"real"...} │
   │ {"player_id":"fran",  "steps_delta":210,"source":"real"...} │
   └─────────────────────────────────────────────────────────────┘
3) +--------+---------+
   | events | players |
   +--------+---------+
   |    142 |       4 |
   +--------+---------+
4) (vacío si no hay eventos rechazados — ideal)
5) users            4 docs   [OK]
   user_balance     4 docs   [OK]
```

#### 💡 Por qué cada paso
- **1)** `gcloud run jobs execute` lanza el Cloud Run Job manualmente. Sin `--wait` la CLI vuelve al prompt de inmediato y no sabes si la ejecución terminó.
- **2)** `subscriptions pull --auto-ack` saca hasta 5 mensajes encolados sin volver a repartirlos → si los ves, la pipeline **publicó** bien. Si sale vacío, el fetcher no publicó (mira los logs del Job).
- **3)** La consulta a `player_scoring_events` prueba que **Dataflow** consumió los mensajes, pasó el anti-trampa y los escribió. Sólo escanea 1 partición (~€0).
- **4)** La DLQ concentra eventos rechazados por velocidad > 15 km/h, JSON malos o cap diario excedido. Si `rejection_reason = anti_cheat_speed` → alguien está simulando pasos falsos.
- **5)** `verificar_demo.sh` confirma que `user_balance` pasó a tener armies+gold actualizados — el pipeline Dataflow es el único que los escribe ahora.

Si los 5 pasos devuelven datos → **la pipeline de tiempo real está operativa**.
A partir de ese momento, cada hora **los jugadores reciben automáticamente los
puntos de los pasos reales que caminó el repo `random_tracker` ese día**.

### 7.10 — Lectura recomendada

- **Notebook Álvaro**, sección **🛰️ Parte B** — ejecución celda a celda (17 celdas con verificación).
- **`steps_ingestor/README.md`** — decisiones de diseño y arquitectura del componente.
- **Terraform `11_steps_ingestor.tf`** — cada recurso comentado con "por qué" y no sólo "qué".

---

## 8. Terraform: qué hace cada archivo

Hemos dividido el terraform en 15 archivos temáticos (en vez de un solo `main.tf`
monolítico) para que sea más fácil de leer y modificar:

| Archivo | Qué crea | Por qué está separado |
|---|---|---|
| `providers.tf` | Provider Google + backend GCS | Configuración global |
| `variables.tf` | Inputs (project_id, region, secrets, params del juego) | Lo primero que lees |
| `01_apis.tf` | Habilita 12 APIs de GCP | Nada funciona sin esto |
| `02_pubsub.tf` | 3 topics + 3 subscriptions | Contrato con el equipo |
| `03_firestore.tf` | Database con delete-protection + PITR | Datos operativos |
| `04_bigquery.tf` | Dataset `cloudrisk` + 3 tablas (`player_scoring_events`, `environmental_factors`, `dead_letter`) | Analytics + DLQ |
| `05_artifact_registry.tf` | Repo Docker privado | Imágenes de servicios |
| `06_secrets.tf` | `cloudrisk-jwt-secret`, `scheduler-secret`, `openweather-api-key` | Nunca en código |
| `07_iam.tf` | 5 Service Accounts + permisos mínimos (incl. dataflow-worker) | Seguridad |
| `08_cloud_run.tf` | 4 services (api, web, air, weather) + 1 job (walker) | Compute |
| `09_scheduler.tf` | Cron de decay/resolve + fetch diario del tracker | Automatización |
| `10_demo_seed.tf` | Job efímero que corre `sembrar_demo.py` | Demo lista tras apply |
| `11_steps_ingestor.tf` | Cloud Run Job del fetcher + IAM + Scheduler diario | Ingesta tracker |
| `12_dataflow.tf` | Flex Template build + `google_dataflow_flex_template_job` del pipeline unificado | Streaming |
| `outputs.tf` | URLs + IDs al terminar | Integración scripts |

> **Cambio 2026-04:** el archivo `11_steps_ingestor.tf` ya no crea el Cloud
> Run Service del scorer horario ni su Scheduler — esa lógica vive ahora
> en el job de Dataflow de `12_dataflow.tf`. El antiguo recurso
> `cloudrisk-dashboard` (Streamlit) también desapareció.

**Cada archivo está comentado en español** para un junior de data engineer —
puedes abrirlo y entender qué hace cada resource sin mirar la doc oficial.

**Para destruir todo** (cuidado, borra TU proyecto GCP):

```bash
# 1. Primero desactivar la delete-protection de Firestore (manual)
gcloud firestore databases update --database='(default)' --delete-protection-state=DELETE_PROTECTION_DISABLED

# 2. Destruir el resto con Terraform
cd infrastructure/terraform
terraform destroy
```

---

## 9. Firestore — esquema y contrato

### 8.1 Contrato compartido (con Álvaro, Noelia, Martha)

Estas 2 colecciones son **el contrato**. No se pueden renombrar ni cambiar
su schema sin acuerdo de todo el equipo.

```
user_balance/{player_id}
├── armies         int     # tropas disponibles para desplegar
├── total_steps    int     # acumulado de pasos del jugador
└── updated_at     str     # ISO timestamp

location_balance/{zone_id}
├── armies         int     # tropas defensoras en la zona
├── owner          str     # player_id actual (o null si libre)
└── updated_at     str     # ISO timestamp
```

### 8.2 Colecciones extendidas (sólo las lee nuestro backend)

```
users/{player_id}           # perfil completo (email, level, gold, clan_color, …)
zones/{zone_id}             # geojson, name, conquered_at, defense_level, …
clans/{clan_id}             # miembros, colour, total_power (legacy — no se usa en v3)
battles/{battle_id}         # historial de combates
step_logs/{log_id}          # raw step events (para analytics)
```

### 8.3 Topics Pub/Sub

```
player-movements    {player_id, lat, lng, steps, timestamp}   # ← Fran
air-quality         {zone_id, pm25, pm10, no2, timestamp}     # ← Álvaro
weather             {zone_id, temp_c, wind_kmh, timestamp}    # ← Álvaro
```

Todos en formato JSON UTF-8. Schema exacto en `pipelines/schemas/`.

### 8.4 Tablas BigQuery

```
cloudrisk.player_scoring_events     # evento por evento (lo escribe cloudrisk_unified)
cloudrisk.environmental_factors     # air+weather fusionados (lo escribe el mismo pipeline)
cloudrisk.dead_letter               # eventos rechazados (anti-trampa, JSON mal formado)
cloudrisk.user_actions              # append-only de acciones (place/attack/conquer/fortify — opcional)
```

**Parámetros del juego** (env vars leídas por el pipeline y el backend):

| Var | Default | Efecto |
|---|---|---|
| `POWER_PER_STEPS` | `500` | Pasos necesarios para 1 army |
| `DAILY_ARMY_CAP` | `50` | Tope armies/día por jugador |
| `DAILY_STEPS_CAP` | `30000` | Tope pasos contables/día (anti-trampa) |
| `MAX_SPEED_KMH` | `15` | Umbral velocidad (> 15 → DLQ) |
| `MIN_GARRISON` | `2` | Invariante: toda zona con owner mantiene ≥ 2 armies |

---

## 10. Backup y restore de Firestore

Firestore NO tiene backup automático en free tier. Protegemos el proyecto con 3 capas:

### 9.1 Delete Protection (protección anti-accidente)

Ya la activa Terraform (`03_firestore.tf`). Cualquier `firestore databases delete`
ahora falla con un mensaje claro. Reversible.

### 9.2 Point-in-Time Recovery (rolling 7 días)

Ya la activa Terraform. Coste: ~0.01 €/mes con nuestros 200 KB de datos.

Restore a cualquier momento en los últimos 7 días:

```bash
gcloud firestore databases restore \
  --source-backup=RESTORE_POINT \
  --destination-database=cloudrisk-recovered
```

### 9.3 Export a GCS (snapshot congelado manual)

```bash
gsutil mb -l europe-west1 gs://cloudrisk-492619-backups

gcloud firestore export \
  gs://cloudrisk-492619-backups/firestore-$(date +%Y%m%d-%H%M%S) \
  --database='(default)' \
  --collection-ids=users,zones,user_balance,location_balance
```

### 9.4 Restore desde un export

```bash
gcloud firestore import gs://cloudrisk-492619-backups/firestore-20260416-030000
```

---

## 11. Demo accounts + comandos de dev

### Demo accounts (4 comandantes pre-seedeados)

Auto-seedeados al arrancar con `USE_LOCAL_STORE=1`:

| Email | Password | Facción |
|---|---|---|
| `norte@cloudrisk.app` | `demo1234` | Norte |
| `sur@cloudrisk.app` | `demo1234` | Sur |
| `este@cloudrisk.app` | `demo1234` | Este |
| `oeste@cloudrisk.app` | `demo1234` | Oeste |

Auto-login por defecto: Norte. Override: `?player=sur`, `?player=este`, `?player=oeste`.

### Comandos útiles

| Qué | Comando |
|---|---|
| Tests backend | `cd backend && USE_LOCAL_STORE=1 SECRET_KEY=dev python -m pytest -v` |
| Build frontend | `cd frontend && npm run build` |
| Simular partida completa | `python data_generator/simulacion_multijugador.py --runs 3` |
| Semillar Firestore | `python scripts/sembrar_firestore.py --team-schema` |
| Pipeline local (DirectRunner) | ver `notebooks/03_noelia_martha_pipeline.ipynb` celda 2 |
| Export a repo del equipo | `bash scripts/sync_to_team_repo.sh --all` |

---

## 12. CI/CD con Cloud Build

**Push a `main` → Cloud Build trigger → redeploy automático.**

Configuración en `CICD/cloudbuild.yaml`. El trigger se configura una vez con:

```bash
gcloud builds triggers create github \
  --repo-name=DTP2-SAFE \
  --repo-owner=RicardoEdreiraPenas \
  --branch-pattern="^main$" \
  --build-config=CICD/cloudbuild.yaml \
  --name=cloudrisk-main-deploy
```

El pipeline:

1. Corre los tests backend (pytest)
2. Compila las imágenes Docker en paralelo (backend, frontend, air, weather, walker, steps-fetcher)
3. Las sube a Artifact Registry
4. Re-despliega los Cloud Run services
5. Ejecuta un smoke test contra `/health` y `/api/v1/analytics/top-steps-month`

---

## 13. Fusión con el repo del equipo

Este repo está estructurado para mergear limpio en
[`alvarogimenezc/DATA-PROJECT-2-EDEM`](https://github.com/alvarogimenezc/DATA-PROJECT-2-EDEM)
como **6 PRs independientes**, una por owner. Proceso paso a paso en
[`notebooks/05_adaptar_al_equipo.ipynb`](./notebooks/05_adaptar_al_equipo.ipynb).

### Orden recomendado de PRs

| # | Owner | Ruta en DATA-PROJECT-2-EDEM | Contenido |
|---|---|---|---|
| 1 | **Álvaro** | `infrastructure/` | Terraform completo (primero) |
| 2 | Fran | `walker/` | `data_generator/juego_caminante.py` + Dockerfile |
| 3 | Fran | `backend/` + `bq_schemas/` | `backend/cloudrisk_api/` + tests |
| 4 | Álvaro | `air_ingestor/` + `weather_ingestor/` | `weather_airq/*.py` + secretos |
| 5 | Noelia + Martha | `pipelines/` | `pipelines/` completo |
| 6 | Ricardo | `frontend/` | `frontend/` completo |

**Orden importante:** Álvaro PR#1 (infra) debe mergearse ANTES que las demás.

---

## 14. Runbook de incidencias comunes

| Síntoma | Causa probable | Fix |
|---|---|---|
| Backend 401 en `/users/me` | JWT vencido o `SECRET_KEY` cambió | Login de nuevo, invalida token local |
| Frontend pantalla negra | Error JS runtime | F12 → Console → mirar línea roja |
| `/turn/setup` devuelve 403 | Falta header `X-Scheduler-Token` en prod | Inyectarlo (Scheduler ya lo hace automáticamente; en local se permite sin token si `USE_LOCAL_STORE=1`) |
| `/turn/setup` devuelve < 60 zonas | In-memory store desactualizado | Reiniciar backend o lanzar el setup desde el propio frontend |
| Walker no publica | SA sin permiso `pubsub.publisher` | Comprueba `07_iam.tf` aplicado |
| Dataflow no procesa | Worker SA sin acceso a Firestore | IAM: `roles/datastore.user` |
| Eventos en `cloudrisk.dead_letter` con `rejection_reason=anti_cheat_speed` | Simulador con paso muy rápido o bug en `speed_mps` | Revisar el productor — el pipeline funciona como debe |
| Cloud Run 403 | Público no permitido | `allUsers` con `roles/run.invoker` (ver `08_cloud_run.tf`) |
| Firestore queries lentas | Índice compuesto faltante | Consola Firestore → Indexes → Create |
| BigQuery "quota exceeded" | Streaming insert > 100 req/s | El pipeline hace INSERT streaming, agrupa por ventana si hace falta |
| `terraform apply` bloqueado | Lock en state | `terraform force-unlock <LOCK_ID>` |

---

## 15. Checklist de entrega

- [ ] Este README actualizado y serverless-focused
- [ ] 6 cuadernos en `notebooks/`: master + 4 por persona + adapt-to-team + anatomía
- [ ] Tests verdes en CI (`.github/workflows/ci.yml`)
- [ ] Deploy funcional en `cloudrisk-492619`
- [ ] 6 PRs abiertas contra `DATA-PROJECT-2-EDEM`
- [ ] Firestore con delete-protection + PITR + 1 export frozen
- [ ] Terraform state con versioning activado en el bucket
- [ ] Diagrama de arquitectura actualizado (`docs/architecture.svg`)
- [ ] Presentación en `docs/CloudRISK_Presentacion.pptx`
- [ ] Vídeo demo (~ 2 min) grabado

---

## 📚 Fuentes

- [Repo del profesor Javi Briones](https://github.com/jabrio/Serverless_EDEM_2026) — metodología y case study de referencia
- [Repo del profesor a10pepo (Terraform)](https://github.com/a10pepo/EDEM_MDA2526/tree/main/PROFESORES/MDA/TERRAFORM) — estilo modular de Terraform
- [Profesora Adriana Campos](https://github.com/AdrianaC304)
- [Repo oficial del equipo](https://github.com/alvarogimenezc/DATA-PROJECT-2-EDEM) — destino de las 6 PRs finales

---

## 🛡️ Licencia

Proyecto educativo · EDEM 2025/2026 · Uso académico. Preguntar antes de reusar fuera de la cohorte.
