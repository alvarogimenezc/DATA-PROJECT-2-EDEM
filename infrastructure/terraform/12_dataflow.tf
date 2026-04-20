# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 12_dataflow.tf — Pipeline Dataflow unificado (stateful)                 │
# │                                                                         │
# │ Consume los 3 topics Pub/Sub (player-movements, weather, air-quality)  │
# │ y aplica toda la lógica de negocio en un único job streaming:          │
# │                                                                         │
# │   - Validación anti-trampa (velocidad > MAX_SPEED_KMH → DLQ)            │
# │   - Cap de pasos diario DAILY_STEPS_CAP (el exceso se descarta)         │
# │   - Distancia haversine por usuario                                    │
# │   - Multiplicador ambiental (aire × clima) vía side input              │
# │   - Límite diario DAILY_ARMY_CAP con CombiningValueState               │
# │   - Timer REAL_TIME que resetea ambos contadores al cumplir las 24 h   │
# │                                                                         │
# │ Sinks:                                                                  │
# │   - Firestore  (user_balance + users, Increment)                       │
# │   - BigQuery   (player_scoring_events, environmental_factors, DLQ)     │
# │                                                                         │
# │ Se despliega vía Flex Template. Los artefactos (template + workers) se  │
# │ construyen con `gcloud dataflow flex-template build` desde el          │
# │ Dockerfile del pipeline — Terraform solo crea el bucket, la SA y lanza  │
# │ el job con los parámetros.                                              │
# └─────────────────────────────────────────────────────────────────────────┘

# ─── Bucket para artefactos de Dataflow ──────────────────────────────────────
resource "google_storage_bucket" "dataflow" {
  name                        = "${var.project_id}-dataflow"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

# ─── Service Account para los workers de Dataflow ────────────────────────────
resource "google_service_account" "dataflow" {
  account_id   = "cloudrisk-dataflow"
  display_name = "CloudRISK Dataflow Workers"
  description  = "SA con la que corren los workers del pipeline unificado"
}

resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_bq_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_storage_bucket_iam_member" "dataflow_bucket_admin" {
  bucket = google_storage_bucket.dataflow.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow.email}"
}

# ─── Flex Template Job ───────────────────────────────────────────────────────
# El template se construye fuera de Terraform con:
#
#   gcloud dataflow flex-template build \
#     gs://${var.project_id}-dataflow/templates/cloudrisk-unified.json \
#     --image-gcr-path=${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk/dataflow-unified:latest \
#     --sdk-language=PYTHON --flex-template-base-image=PYTHON3 \
#     --metadata-file=pipelines/template_metadata.json \
#     --py-path=pipelines/ \
#     --env=FLEX_TEMPLATE_PYTHON_PY_FILE=pipelines/cloudrisk_unified.py \
#     --env=FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=pipelines/requirements.txt
#
# Luego, Terraform lanza el job:
resource "google_dataflow_flex_template_job" "unified" {
  provider = google-beta
  name     = "cloudrisk-unified"
  region   = var.region

  container_spec_gcs_path = "gs://${google_storage_bucket.dataflow.name}/templates/cloudrisk-unified.json"

  parameters = {
    player_sub    = google_pubsub_subscription.player_movements_sub.id
    weather_sub   = google_pubsub_subscription.weather_sub.id
    airq_sub      = google_pubsub_subscription.air_quality_sub.id
    scoring_table = "${var.project_id}:${google_bigquery_dataset.cloudrisk.dataset_id}.${google_bigquery_table.player_scoring_events.table_id}"
    env_table     = "${var.project_id}:${google_bigquery_dataset.cloudrisk.dataset_id}.${google_bigquery_table.environmental_factors.table_id}"
    dlq_table     = "${var.project_id}:${google_bigquery_dataset.cloudrisk.dataset_id}.${google_bigquery_table.dead_letter.table_id}"

    max_speed_kmh    = tostring(var.max_speed_kmh)
    power_per_steps  = tostring(var.power_per_steps)
    daily_army_cap   = tostring(var.daily_army_cap)
    daily_steps_cap  = tostring(var.daily_steps_cap)

    temp_location      = "gs://${google_storage_bucket.dataflow.name}/tmp"
    staging_location   = "gs://${google_storage_bucket.dataflow.name}/staging"
    serviceAccount     = google_service_account.dataflow.email
    maxWorkers         = "3"
    numWorkers         = "1"
    enableStreamingEngine = "true"
  }

  depends_on = [
    google_project_iam_member.dataflow_worker,
    google_project_iam_member.dataflow_bq_editor,
    google_project_iam_member.dataflow_bq_jobuser,
    google_project_iam_member.dataflow_firestore,
    google_project_iam_member.dataflow_pubsub,
    google_storage_bucket_iam_member.dataflow_bucket_admin,
    google_bigquery_table.player_scoring_events,
    google_bigquery_table.dead_letter,
    null_resource.dataflow_flex_template,
  ]

  # Si alguien modifica parámetros de escalado fuera de Terraform, no
  # forzamos re-creación del job (tirarlo reiniciaría la pipeline).
  lifecycle {
    ignore_changes = [parameters["numWorkers"], parameters["maxWorkers"]]
  }
}

output "dataflow_bucket" {
  value       = google_storage_bucket.dataflow.name
  description = "Bucket GCS para artefactos de Dataflow (templates, tmp, staging)"
}

output "dataflow_job_name" {
  value       = google_dataflow_flex_template_job.unified.name
  description = "Nombre del job Dataflow unificado"
}
