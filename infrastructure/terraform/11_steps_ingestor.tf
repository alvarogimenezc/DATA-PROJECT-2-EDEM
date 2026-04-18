# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 11_steps_ingestor.tf — Ingesta diaria de pasos reales                   │
# │                                                                         │
# │ Este archivo despliega el componente `steps_ingestor/` del repo:        │
# │                                                                         │
# │   1) recolector_pasos_diario  (Cloud Run **Job**)                       │
# │      → 1×/día tira JSON de github.com/FranciscoAlvarezVaras/random_     │
# │        tracker, publica N mensajes al topic player-movements.           │
# │      → Disparado por Cloud Scheduler a las 03:00 Europe/Madrid.         │
# │                                                                         │
# │ El antiguo scorer horario se eliminó: toda su lógica se absorbió en el  │
# │ pipeline Dataflow unificado (pipelines/cloudrisk_unified.py) vía        │
# │ stateful DoFn. Ya no hay Cloud Run Service ni Cloud Scheduler horario.  │
# └─────────────────────────────────────────────────────────────────────────┘

# ─── Service Account dedicada al ingestor ───────────────────────────────────
resource "google_service_account" "steps_ingestor" {
  account_id   = "cloudrisk-steps-ingestor"
  display_name = "CloudRISK Steps Ingestor (random_tracker)"
  description  = "SA que corre el fetcher diario y el scorer horario de pasos reales"
}

# Necesita publicar al topic player-movements
resource "google_pubsub_topic_iam_member" "ingestor_pubsub_publisher" {
  topic  = google_pubsub_topic.player_movements.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.steps_ingestor.email}"
}

# Necesita leer BQ + escribir Firestore
resource "google_project_iam_member" "ingestor_bq_reader" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.steps_ingestor.email}"
}
resource "google_project_iam_member" "ingestor_bq_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.steps_ingestor.email}"
}
resource "google_project_iam_member" "ingestor_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.steps_ingestor.email}"
}

# ─── Cloud Run JOB: fetcher diario ──────────────────────────────────────────
resource "google_cloud_run_v2_job" "steps_fetcher" {
  name     = "cloudrisk-steps-fetcher"
  location = var.region

  template {
    template {
      service_account = google_service_account.steps_ingestor.email
      timeout         = "600s"     # 10 min suficiente para tirar un JSON

      containers {
        # Imagen construida por Cloud Build a partir de steps_ingestor/Dockerfile
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk/steps-ingestor:latest"
        command = ["python", "recolector_pasos_diario.py"]

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "TRACKER_REPO"
          value = "FranciscoAlvarezVaras/random_tracker"
        }
        env {
          name  = "TRACKER_BRANCH"
          value = "main"
        }
        env {
          name  = "TRACKER_FILE"
          value = "movements.json"
        }
        env {
          name  = "PUBSUB_TOPIC"
          value = google_pubsub_topic.player_movements.name
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_pubsub_topic_iam_member.ingestor_pubsub_publisher,
  ]
}

# ─── Cloud Scheduler: fetcher diario a las 03:00 Europe/Madrid ──────────────
resource "google_cloud_scheduler_job" "steps_fetcher_daily" {
  name        = "cloudrisk-steps-fetcher-daily"
  region      = var.region
  description = "Tira random_tracker JSON y publica a player-movements, 1x/día"
  schedule    = "0 3 * * *"
  time_zone   = "Europe/Madrid"

  attempt_deadline = "180s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.steps_fetcher.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job.steps_fetcher,
  ]
}

output "steps_fetcher_job_name" {
  value       = google_cloud_run_v2_job.steps_fetcher.name
  description = "Run-once-daily Cloud Run Job that ingests random_tracker data"
}


