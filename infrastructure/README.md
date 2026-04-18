# infrastructure/

## 🎯 Qué hace este directorio

Aquí vive toda la **infraestructura como código** de CloudRISK sobre GCP. Un solo `terraform apply` levanta (o destruye) el proyecto entero: Firestore, Pub/Sub, BigQuery, Cloud Run, Artifact Registry, IAM, Secret Manager, Cloud Scheduler... todo.

Dos cosas conviven aquí:

- **`terraform/`**: 15 ficheros `.tf` numerados por orden de dependencia. Es el estándar del proyecto.
- **`deploy.sh`**: bootstrap "de los primeros 5 minutos" — habilita APIs, crea el bucket de estado remoto y arranca `terraform init`. Solo lo corres una vez por proyecto nuevo.

**Este README es un resumen** de qué crea cada archivo. El detalle de cada
recurso vive comentado dentro del propio `.tf` (en español, orientado a
lectura línea a línea).

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **Terraform (HCL)** | IaC declarativo oficial para GCP. Mantiene estado, detecta drift, permite `plan` antes de `apply`. Alternativas (gcloud scripts, Pulumi) o bien no guardan estado o añaden un lenguaje extra — Terraform es el punto dulce para un equipo con background mixto. |
| **Proveedor `hashicorp/google`** | Cliente oficial de Google para Terraform. Cubre el 100 % de los servicios que usamos. |
| **Backend GCS** | El `tfstate` se guarda en `gs://${PROJECT_ID}-terraform-state` — así Álvaro, Fran, Noelia, Martha y Ricardo compartimos estado sin pisarnos. |
| **Bash** (solo `deploy.sh`) | Para el bootstrap inicial (habilitar APIs, crear el bucket). Terraform no puede crear el bucket que guarda su propio estado — problema del huevo y la gallina. |

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `deploy.sh` | Bootstrap: habilita APIs de GCP, crea bucket de state, hace `terraform init` + `apply`. |
| `terraform/01_apis.tf` | Habilita APIs necesarias (run, firestore, pubsub, bigquery, artifactregistry, secretmanager, dataflow, iam, scheduler, eventarc, logging). Sin Cloud Build — CI/CD retirado. |
| `terraform/02_pubsub.tf` | Topics y subscriptions: `player-movements`, `weather-events`, `airquality-events` + DLQs. |
| `terraform/03_firestore.tf` | Base de datos Firestore en modo Native, región `eur3`. |
| `terraform/04_bigquery.tf` | Dataset `cloudrisk` con tablas `player_scoring_events`, `environmental_factors`, `dead_letter`. |
| `terraform/05_artifact_registry.tf` | Repo Docker `cloudrisk` donde `gcloud builds submit` sube las imágenes. |
| `terraform/06_secrets.tf` | Secret Manager: `cloudrisk-jwt-secret`, `scheduler-secret`, `openweather-api-key`. |
| `terraform/07_iam.tf` | Service accounts y bindings (backend, walker, dataflow-worker, scheduler). |
| `terraform/08_cloud_run.tf` | Services `cloudrisk-api` y `cloudrisk-web` + Job `cloudrisk-walker`. |
| `terraform/09_scheduler.tf` | Cloud Scheduler: cron diario del fetcher de pasos + cron de `/turn/advance` y `/battles/resolve-expired`. |
| `terraform/10_demo_seed.tf` | Job efímero que corre `sembrar_demo.py` tras el apply. |
| `terraform/11_steps_ingestor.tf` | Cloud Run Job (daily fetcher) del `steps_ingestor/`. |
| `terraform/12_dataflow.tf` | Flex Template + `google_dataflow_flex_template_job` que despliega `pipelines/cloudrisk_unified.py`. |
| `terraform/providers.tf` | Config del backend GCS + provider `google`. |
| `terraform/variables.tf` / `terraform.tfvars` | Inputs: `project_id`, `region`, etc. (el `.example` es la plantilla). |
| `terraform/outputs.tf` | URLs de Cloud Run + nombres de topics que otros scripts consumen. |

## 🔗 Cómo se conecta con el resto del proyecto

```
infrastructure/deploy.sh  ──▶  terraform init/apply
                                      │
                                      ▼
                    Todos los recursos GCP que necesitan:
                                      │
     ┌────────────────┬────────────────┬──────────────────┬─────────────────┐
     ▼                ▼                ▼                  ▼                 ▼
backend/         frontend/        pipelines/         data_generator/   steps_ingestor/
(Cloud Run)    (Cloud Run)     (Dataflow Job)      (Cloud Run Job)    (Cloud Run Job)
                                      │
                                      ▼
                              (build manual con `gcloud builds submit`
                               por servicio — sin wrapper CI/CD)
```

> **Cambio 2026-04:** desaparecen de Terraform los recursos del antiguo
> `cloudrisk-hourly-scorer` (Cloud Run Service + Scheduler horario), del
> dashboard Streamlit (`cloudrisk-dashboard`) y de Cloud Build. Toda la lógica
> de scoring vive ahora en el job de Dataflow definido en `12_dataflow.tf`;
> la analítica se sirve desde el backend (`/api/v1/analytics/*`).

### Variables relevantes (juego + pipeline)

Definidas en `variables.tf` y consumidas por `12_dataflow.tf` (Flex Template):

| Variable | Default | Uso |
|---|---|---|
| `power_per_steps` | `500` | Pasos necesarios para 1 army |
| `daily_army_cap` | `50` | Máx armies/día por jugador |
| `daily_steps_cap` | `30000` | Máx pasos contables/día (anti-trampa) |
| `max_speed_kmh` | `15` | Umbral anti-trampa |
| `scheduler_secret` | (random) | Token para endpoints internos (`/turn/setup`, `/battles/resolve-expired`) |

- Sin `terraform apply` no hay **nada** desplegado — ni topics, ni BD, ni registro de imágenes.
- El seed de Firestore se dispara automáticamente desde `10_demo_seed.tf`
  (llama a `scripts/sembrar_demo.py`). Para re-sembrar manualmente:
  `python scripts/sembrar_demo.py --project <ID>`.

## 🚀 Cómo ejecutarlo

```bash
# Bootstrap inicial (primera vez en un proyecto nuevo)
export JWT_SECRET=$(openssl rand -hex 32)
bash infrastructure/deploy.sh cloudrisk-492619 europe-west1

# Ciclo normal una vez bootstrapped (lo que harás el 95 % del tiempo)
cd infrastructure/terraform
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars

# Destruir todo (cuidado — se lleva Firestore, BigQuery, todo)
terraform destroy -var-file=terraform.tfvars

# Ver outputs (URLs públicas de cada servicio)
terraform output
```
