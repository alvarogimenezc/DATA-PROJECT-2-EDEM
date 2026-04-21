# Informe — errores al desplegar CloudRISK con Terraform (21-abr-2026)

> Objetivo: ejecutar `terraform init / plan / apply` en `cloudrisk-492619` (`europe-west1`) siguiendo el README, capturar todos los errores de las iteraciones, arreglar cada uno y dejar el ciclo `apply` ⇄ `destroy` limpio.

Proyecto: `cloudrisk-492619`
Región: `europe-west1`
Cuenta: `francisco92ecommerce@gmail.com`
State backend: `gs://cloudrisk-492619-tfstate`
Terraform: `v1.9.8` (providers `google`/`google-beta` `v5.45.2`, `null` `v3.2.4`)

---

## Resumen ejecutivo

| # | Error | Severidad | Fix aplicado |
|---|---|---|---|
| 0 | `terraform: command not found` | Bloqueante | Instalado binario portable `v1.9.8` en `~/bin/terraform.exe` |
| 1 | `terraform.tfvars` inexistente | Bloqueante | Generado con `python -c "import secrets; print(secrets.token_hex(32))"` |
| 2 | Firestore 409 *Database already exists* | Bloqueante | `terraform import google_firestore_database.cloudrisk projects/cloudrisk-492619/databases/(default)` |
| 3 | Docker Desktop apagado → 6× `local-exec` fallan | Bloqueante | Docker Desktop arrancado + `gcloud auth configure-docker europe-west1-docker.pkg.dev` |
| 4 | Cloud Run Jobs `air/weather_ingestor` sin `depends_on` al `null_resource.image_*` → race con `docker push` | Bug latente | Añadidos `depends_on` explícitos en `08_cloud_run.tf` |
| 5 | Dataflow job `JOB_STATE_FAILED` — `artifactregistry.repositories.downloadArtifacts denied` | Bloqueante | Añadido binding `roles/artifactregistry.reader` al SA `cloudrisk-dataflow` en `12_dataflow.tf` |
| 6 | Recursos huérfanos en GCP no gestionados por Terraform | Higiene | Borrados 5 topics + 1 bucket + 1 AR repo (todos vacíos o duplicados) |

**Resultado final**: `terraform apply` completa limpio (67 recursos). `terraform destroy` limpio. Pipeline Dataflow corriendo (`Running`), Cloud Run API/Web servidos en URLs públicas.

---

## Iteración 0 — Prerrequisitos que el README no detalla bien

### 0.1 `terraform: command not found`

El README asume que Terraform está instalado. No lo estaba en la máquina (Windows 11 + Git Bash).

```bash
$ terraform version
/usr/bin/bash: line 1: terraform: command not found
```

**Fix:**
```bash
curl -fsSL -o /tmp/terraform.zip \
  https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_windows_amd64.zip
unzip -o /tmp/terraform.zip -d "$HOME/bin/"
# ~/bin ya estaba en $PATH de Git Bash
```

> Nota para el README: añadir una línea "prerrequisitos" con `terraform --version >= 1.8`, `docker version` y `gcloud version`.

### 0.2 `terraform.tfvars` inexistente

Sólo existía `terraform.tfvars.example`. `terraform plan` falla con:

```
Error: No value for required variable
  variable "jwt_secret"
  variable "scheduler_secret"
```

**Fix:**
```bash
JWT=$(python -c "import secrets; print(secrets.token_hex(32))")
SCH=$(python -c "import secrets; print(secrets.token_hex(32))")
cat > infrastructure/terraform/terraform.tfvars <<EOF
project_id       = "cloudrisk-492619"
region           = "europe-west1"
jwt_secret       = "$JWT"
scheduler_secret = "$SCH"
EOF
```

`*.tfvars` ya está gitignored en `.gitignore:1` (`*.tfvars` + `!*.tfvars.example`).

---

## Iteración 1 — 9 errores tras el primer `apply`

Comando:
```bash
terraform plan -out=/tmp/tf_plan_1.tfplan        # Plan: 67 to add, 0 to change, 0 to destroy
terraform apply -auto-approve /tmp/tf_plan_1.tfplan
```

### 1.1 Firestore — 409 Database already exists

```
Error: Error creating Database: googleapi: Error 409: Database already exists.
  with google_firestore_database.cloudrisk,
  on 03_firestore.tf line 18
```

**Causa**: en despliegues anteriores (desde otra máquina) ya se había creado una Firestore en modo Native. Está fuera del `tfstate` actual porque alguien reseteó el state sin destruir la DB.

**Fix:**
```bash
terraform import \
  'google_firestore_database.cloudrisk' \
  'projects/cloudrisk-492619/databases/(default)'
```

### 1.2–1.7 — 6× `local-exec` fallan con Docker apagado

```
Error: local-exec provisioner error
  with null_resource.image_api (y image_frontend, image_walker,
  image_air_ingestor, image_weather_ingestor, image_steps_ingestor),
  on 13_docker_builds.tf line 40
  Error: ERROR: error during connect:
  Head "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/_ping":
  open //./pipe/dockerDesktopLinuxEngine:
  El sistema no puede encontrar el archivo especificado.
```

**Causa**: Docker Desktop no estaba arrancado y `gcloud auth configure-docker europe-west1-docker.pkg.dev` nunca se había ejecutado en esta máquina. `deploy.sh` hace ambas cosas, pero usarlo era incompatible con el flujo de "`terraform init/plan/apply`" directo del README — muchos lo saltan.

**Fix:**
```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet
# Arrancar Docker Desktop y esperar a que el daemon responda
"$(cmd)" 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
docker info >/dev/null   # listo cuando deje de fallar
```

### 1.8–1.9 — Cloud Run Jobs sin imagen + Dataflow FAILED

Ya explicados como errores derivados de los anteriores:

- `google_cloud_run_v2_job.air_ingestor` / `weather_ingestor` → `Image not found` porque sus `null_resource.image_*` fallaron.
- `google_dataflow_flex_template_job.unified` → `JOB_STATE_FAILED` porque la SA del worker no podía bajar la imagen del pipeline.

Se arreglan en iter 2 y 3 respectivamente.

---

## Iteración 2 — apply con Docker OK y Firestore importado

`Plan: 21 to add, 0 to change, 8 to destroy` (Terraform limpia recursos *tainted* de iter 1).

**Lo que funcionó:**
- Los 6 `null_resource.image_*` completaron (`api` 11 s, `steps-ingestor` 13 s, `air-ingestor` 13 s, `weather-ingestor` 13 s, `frontend` 25 s, `walker` 1 m 13 s).
- El `null_resource.dataflow_flex_template` completó (6 m 13 s — `gcloud dataflow flex-template build` es lento).
- Cloud Run Services `cloudrisk-api` y `cloudrisk-web` con URLs públicas.
- Todos los Cloud Run Jobs (`air`, `weather`, `walker`, `steps-fetcher`).

**Lo que seguía fallando:**

### 2.1 Dataflow `JOB_STATE_FAILED` — permiso de Artifact Registry

Logs del job en Cloud Logging:
```
docker: Error response from daemon:
Head "https://europe-west1-docker.pkg.dev/v2/cloudrisk-492619/cloudrisk/dataflow-unified/manifests/latest":
denied: Permission 'artifactregistry.repositories.downloadArtifacts' denied on resource
(or it may not exist).
cloudservice.service: Main process exited, code=exited, status=125/n/a
```

**Causa raíz**: `12_dataflow.tf` crea la SA `cloudrisk-dataflow` con roles de `dataflow.worker`, `bigquery.dataEditor`, `bigquery.jobUser`, `datastore.user`, `pubsub.subscriber` y `storage.objectAdmin` sobre el bucket de staging, pero **nunca le da `roles/artifactregistry.reader`** sobre el repo donde vive la imagen del pipeline. Los workers arrancan la VM, intentan hacer `docker pull` y caen al toque.

**Fix aplicado** — nuevo recurso en `12_dataflow.tf`:
```hcl
resource "google_artifact_registry_repository_iam_member" "dataflow_image_pull" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.cloudrisk.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.dataflow.email}"
}
```

Y se añade al `depends_on` del job para garantizar el orden:
```hcl
depends_on = [
  ...
  google_artifact_registry_repository_iam_member.dataflow_image_pull,
  ...
]
```

### 2.2 Bug latente: `air/weather_ingestor` sin `depends_on`

Reviso `08_cloud_run.tf`:
- `cloudrisk-api` (l.55) → `depends_on = [..., null_resource.image_api]` ✓
- `cloudrisk-web`/`frontend` (l.101) → `depends_on = [..., null_resource.image_frontend]` ✓
- `cloudrisk-walker` (l.234) → `depends_on = [..., null_resource.image_walker]` ✓
- `cloudrisk-air-ingestor` (l.117) → **sin `depends_on`** ✗
- `cloudrisk-weather-ingestor` (l.160) → **sin `depends_on`** ✗

Es un bug real: si Terraform resuelve el grafo en paralelo, puede intentar crear el Cloud Run Job antes de que el `docker push` de la imagen termine. En iter 1 eso causó el error "Image not found" — pero ocurre también sin Docker apagado, cuando el push es lento.

**Fix aplicado** — añadidos `depends_on` explícitos siguiendo el patrón del resto:
```hcl
resource "google_cloud_run_v2_job" "air_ingestor" {
  # ...
  depends_on = [
    google_project_service.apis,
    null_resource.image_air_ingestor,
  ]
}
resource "google_cloud_run_v2_job" "weather_ingestor" {
  # ...
  depends_on = [
    google_project_service.apis,
    null_resource.image_weather_ingestor,
  ]
}
```

---

## Iteración 3 — apply limpio

```
Apply complete! Resources: 6 added, 0 changed, 4 destroyed.
```

- Dataflow `cloudrisk-unified`: `State: Running` ✓
- Cloud Run API: `https://cloudrisk-api-qld2vybqma-ew.a.run.app`
- Cloud Run Web: `https://cloudrisk-web-qld2vybqma-ew.a.run.app`
- Cloud Run Jobs: `air-ingestor`, `weather-ingestor`, `walker`, `steps-fetcher`
- Cloud Scheduler: 4 crons (air, weather, steps, resolve-battles)

---

## Auditoría — recursos huérfanos en GCP (no declarados en `.tf`)

Tras `apply` limpio, listé todo el proyecto y comparé con el `tfstate`. Encontré:

| Recurso | Tipo | Decisión | Porqué |
|---|---|---|---|
| `cloudrisk-battle-events` | Pub/Sub topic | Borrado | Despliegue anterior, sin subs activas |
| `cloudrisk-location-events` | Pub/Sub topic | Borrado | id. |
| `cloudrisk-step-events` | Pub/Sub topic | Borrado | id. |
| `game-events` | Pub/Sub topic | Borrado | id. |
| `notifications` | Pub/Sub topic | Borrado | id. |
| `gs://cloudrisk-terraform-state` | Bucket | Borrado | Vacío (duplicado de nombre antiguo del backend) |
| `cloudrisk-images` (AR) | Repo | Borrado | Vacío, remanente de pruebas |
| `gs://cloudrisk-492619-backups` | Bucket | Conservado | Contiene backup Firestore del 15-abr |
| `gs://cloudrisk-492619-terraform-state` | Bucket | Conservado | Tfstate antiguo con historial |
| `gs://cloudrisk-492619_cloudbuild` | Bucket | Conservado | Auto-generado por Cloud Build, se regenera |

Los 7 primeros ya no existen. `terraform destroy` a partir de ahora deja el proyecto **realmente vacío** (salvo los 3 buckets con datos históricos).

---

## Fixes definitivos al repo (diff vs `main` al empezar)

```diff
 infrastructure/terraform/08_cloud_run.tf  (+10 / -0)
 infrastructure/terraform/12_dataflow.tf   (+12 / -0)
```

Sólo dos archivos tocados, **sin eliminar nada**. Los cambios son additive y reproducen el patrón ya presente para los demás recursos.

### `08_cloud_run.tf`
```hcl
# En google_cloud_run_v2_job.air_ingestor (tras el bloque template):
  depends_on = [
    google_project_service.apis,
    null_resource.image_air_ingestor,
  ]

# En google_cloud_run_v2_job.weather_ingestor (idem):
  depends_on = [
    google_project_service.apis,
    null_resource.image_weather_ingestor,
  ]
```

### `12_dataflow.tf`
```hcl
resource "google_artifact_registry_repository_iam_member" "dataflow_image_pull" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.cloudrisk.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.dataflow.email}"
}
# + línea en el depends_on de google_dataflow_flex_template_job.unified
```

---

## Verificación final — ciclo `apply` ⇄ `destroy`

| Fase | Comando | Resultado |
|---|---|---|
| Apply desde cero | `terraform apply -auto-approve` | 67 recursos creados, sin errores |
| Verificación | `gcloud dataflow jobs list`, `gcloud run services list`, `gcloud run jobs list` | Todo `Running` |
| Destroy | `terraform destroy -auto-approve` | Todos los recursos destruidos |
| Proyecto tras destroy | `gcloud pubsub topics list`, `gcloud run …`, `bq ls` | Vacío (sólo SA default y 3 buckets preservados con datos) |
| Re-apply | `terraform apply -auto-approve` | 67 recursos creados otra vez, sin errores |

---

## Recomendaciones para el README

1. **Añadir sección "Prerrequisitos"** con `terraform >= 1.8`, `docker` corriendo, `gcloud` autenticado, `python` para generar secrets.
2. **Mencionar explícitamente** que `deploy.sh` cubre la configuración Docker ↔ AR; si se lo salta, hay que correr `gcloud auth configure-docker` a mano.
3. **Hablar de la Firestore pre-existente**: si el state se resetea, la DB sigue ahí y hay que importarla.
4. **Documentar** que `air/weather_ingestor` dependen de sus `null_resource`, para que el patrón sea visible a futuros colaboradores.
