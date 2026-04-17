# infrastructure/

## 🎯 Qué hace este directorio

Aquí vive toda la **infraestructura como código** de CloudRISK sobre GCP. Un solo `terraform apply` levanta (o destruye) el proyecto entero: Firestore, Pub/Sub, BigQuery, Cloud Run, Artifact Registry, IAM, Secret Manager, Cloud Scheduler... todo.

Dos cosas conviven aquí:

- **`terraform/`**: 14 ficheros `.tf` numerados por orden de dependencia. Es el estándar del proyecto.
- **`deploy.sh`**: bootstrap "de los primeros 5 minutos" — habilita APIs, crea el bucket de estado remoto y arranca `terraform init`. Solo lo corres una vez por proyecto nuevo.

**Este README es un resumen.** Toda la explicación detallada de qué hace cada recurso, cómo se conectan y troubleshooting vive en `notebooks/TERRAFORM_Y_GCP_REFERENCIA.md` — no dupliques cosas aquí.

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
| `terraform/01_apis.tf` | Habilita APIs necesarias (run, firestore, pubsub, bigquery, artifactregistry, secretmanager...). |
| `terraform/02_pubsub.tf` | Topics y subscriptions: `player-movements`, `weather-events`, `airquality-events` + DLQs. |
| `terraform/03_firestore.tf` | Base de datos Firestore en modo Native, región `eur3`. |
| `terraform/04_bigquery.tf` | Datasets `cloudrisk_metrics` y `cloudrisk`, tablas de step_events y environmental_factors. |
| `terraform/05_artifact_registry.tf` | Repo Docker `cloudrisk-images` donde Cloud Build sube las imágenes. |
| `terraform/06_secrets.tf` | Secret Manager: `JWT_SECRET`, credenciales del tracker externo. |
| `terraform/07_iam.tf` | Service accounts y bindings (backend, walker, scorer, scheduler). |
| `terraform/08_cloud_run.tf` | Services `cloudrisk-api`, `cloudrisk-dashboard`, `cloudrisk-web` + Job `cloudrisk-walker`. |
| `terraform/09_scheduler.tf` | Cloud Scheduler: cron diario del fetcher, cron horario del scorer. |
| `terraform/10_demo_seed.tf` | Job efímero que corre `sembrar_demo.py` tras el apply. |
| `terraform/11_steps_ingestor.tf` | Cloud Run Job (daily fetcher) + Service (hourly scorer) del `steps_ingestor/`. |
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
     ┌────────────────┬────────────────┼────────────────┬─────────────────┐
     ▼                ▼                ▼                ▼                 ▼
backend/         frontend/        dashboard/      data_generator/    steps_ingestor/
(Cloud Run)    (Cloud Run)      (Cloud Run)       (Cloud Run Job)   (Job + Service)
                                      │
                                      ▼
                              CICD/cloudbuild.yaml
                         (el trigger lo crea 08_cloud_run.tf)
```

- Sin `terraform apply` no hay **nada** desplegado — ni topics, ni BD, ni registro de imágenes.
- Después del apply usas `bash CICD/sembrar_demo.sh` para poblar Firestore.
- **Detalle completo** de cada recurso, variables y troubleshooting → `notebooks/TERRAFORM_Y_GCP_REFERENCIA.md`.

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
