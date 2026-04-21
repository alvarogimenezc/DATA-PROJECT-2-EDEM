# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 13_docker_builds.tf — Build & push de imágenes Docker desde Terraform   │
# │                                                                         │
# │ El profe pide: "deployed seamlessly with a single terraform apply".     │
# │ Cloud Run y Dataflow necesitan imágenes ya subidas al Artifact          │
# │ Registry. Aquí las construimos y las pusheamos con `null_resource` +    │
# │ `local-exec` — un paso Terraform que ejecuta comandos locales.          │
# │                                                                         │
# │ 7 null_resources:                                                       │
# │   - 6 para las imágenes de servicios/jobs (api, frontend, ingestors)    │
# │   - 1 para el flex template de Dataflow                                 │
# │                                                                         │
# │ Cada null_resource tiene un `triggers` con el filemd5 del Dockerfile    │
# │ (y del requirements.txt cuando aplica). Si NADA de eso cambia,          │
# │ Terraform no rebuildea. Si cambias una línea → rebuild automático.      │
# │                                                                         │
# │ Pre-requisitos (los deja listos `infrastructure/deploy.sh`):            │
# │   - Docker corriendo localmente                                         │
# │   - gcloud auth configure-docker ya ejecutado                           │
# │   - El Artifact Registry existe (depends_on al 05_artifact_registry)    │
# └─────────────────────────────────────────────────────────────────────────┘

locals {
  # Ruta base del registry de este proyecto — mismo patrón que 08_cloud_run.tf
  registry = "${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk"

  # Raíz del repo (dos niveles arriba de infrastructure/terraform)
  repo_root = "${path.module}/../.."
}

# =============================================================================
# IMG 1/6 — cloudrisk-api (backend FastAPI)
# =============================================================================
resource "null_resource" "image_api" {
  triggers = {
    dockerfile   = filemd5("${local.repo_root}/backend/Dockerfile")
    requirements = filemd5("${local.repo_root}/backend/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "docker build -t ${local.registry}/api:latest ${local.repo_root}/backend && docker push ${local.registry}/api:latest"
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_artifact_registry_repository.cloudrisk]
}

# =============================================================================
# IMG 2/6 — cloudrisk-web (frontend React + Vite)
# =============================================================================
resource "null_resource" "image_frontend" {
  triggers = {
    dockerfile = filemd5("${local.repo_root}/frontend/Dockerfile")
    package    = filemd5("${local.repo_root}/frontend/package.json")
    api_url    = google_cloud_run_v2_service.api.uri
  }

  provisioner "local-exec" {
    command     = "docker buildx build --platform linux/amd64 --provenance=false --push --build-arg VITE_API_URL=${google_cloud_run_v2_service.api.uri} -t ${local.registry}/frontend:latest ${local.repo_root}/frontend"
    interpreter = ["bash", "-c"]
  }

  depends_on = [
    google_artifact_registry_repository.cloudrisk,
    google_cloud_run_v2_service.api,
  ]
}

# =============================================================================
# IMG 3/6 — cloudrisk-air-ingestor (weather_airq/ con --target=air)
# =============================================================================
# El Dockerfile de weather_airq es multi-stage: un stage llamado `air` con
# calidad_aire.py y otro `weather` con clima.py. Compartimos imagen base.
resource "null_resource" "image_air_ingestor" {
  triggers = {
    dockerfile   = filemd5("${local.repo_root}/weather_airq/dockerfile")
    requirements = filemd5("${local.repo_root}/weather_airq/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "docker build -f ${local.repo_root}/weather_airq/dockerfile --target air -t ${local.registry}/air-ingestor:latest ${local.repo_root}/weather_airq && docker push ${local.registry}/air-ingestor:latest"
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_artifact_registry_repository.cloudrisk]
}

# =============================================================================
# IMG 4/6 — cloudrisk-weather-ingestor (weather_airq/ con --target=weather)
# =============================================================================
resource "null_resource" "image_weather_ingestor" {
  triggers = {
    dockerfile   = filemd5("${local.repo_root}/weather_airq/dockerfile")
    requirements = filemd5("${local.repo_root}/weather_airq/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "docker build -f ${local.repo_root}/weather_airq/dockerfile --target weather -t ${local.registry}/weather-ingestor:latest ${local.repo_root}/weather_airq && docker push ${local.registry}/weather-ingestor:latest"
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_artifact_registry_repository.cloudrisk]
}

# =============================================================================
# IMG 5/6 — cloudrisk-walker (data_generator/ — simula pasos)
# =============================================================================
resource "null_resource" "image_walker" {
  triggers = {
    dockerfile   = filemd5("${local.repo_root}/data_generator/Dockerfile")
    requirements = filemd5("${local.repo_root}/data_generator/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "docker build -t ${local.registry}/walker:latest ${local.repo_root}/data_generator && docker push ${local.registry}/walker:latest"
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_artifact_registry_repository.cloudrisk]
}

# =============================================================================
# IMG 6/6 — cloudrisk-steps-ingestor (steps_ingestor/ — fetcher diario)
# =============================================================================
resource "null_resource" "image_steps_ingestor" {
  triggers = {
    dockerfile   = filemd5("${local.repo_root}/steps_ingestor/Dockerfile")
    requirements = filemd5("${local.repo_root}/steps_ingestor/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "docker build -t ${local.registry}/steps-ingestor:latest ${local.repo_root}/steps_ingestor && docker push ${local.registry}/steps-ingestor:latest"
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_artifact_registry_repository.cloudrisk]
}

# =============================================================================
# DATAFLOW — Flex template (pipelines/cloudrisk_unified.py)
# =============================================================================
# gcloud dataflow flex-template build hace 3 cosas:
#   1) Construye imagen Docker con el pipeline + sus deps
#   2) La pushea al Artifact Registry
#   3) Sube un manifiesto JSON al bucket GCS de Dataflow
# Terraform luego usa ese manifiesto en 12_dataflow.tf para lanzar el job.
resource "null_resource" "dataflow_flex_template" {
  triggers = {
    pipeline     = filemd5("${local.repo_root}/pipelines/cloudrisk_unified.py")
    requirements = filemd5("${local.repo_root}/pipelines/requirements.txt")
  }

  provisioner "local-exec" {
    command     = <<-EOT
      gcloud dataflow flex-template build \
        "gs://${google_storage_bucket.dataflow.name}/templates/cloudrisk-unified.json" \
        --image-gcr-path "${local.registry}/dataflow-unified:latest" \
        --sdk-language=PYTHON \
        --flex-template-base-image=PYTHON3 \
        --py-path="${local.repo_root}/pipelines/" \
        --env "FLEX_TEMPLATE_PYTHON_PY_FILE=cloudrisk_unified.py" \
        --env "FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=requirements.txt"
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [
    google_artifact_registry_repository.cloudrisk,
    google_storage_bucket.dataflow,
  ]
}
