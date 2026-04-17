# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 11_steps_ingestor.tf — Ingesta diaria + scoring horario de pasos reales │
# │                                                                         │
# │ Este archivo despliega el componente `steps_ingestor/` del repo:        │
# │                                                                         │
# │   1) recolector_pasos_diario  (Cloud Run **Job**)                       │
# │      → 1×/día tira JSON de github.com/FranciscoAlvarezVaras/random_     │
# │        tracker, publica N mensajes al topic player-movements.           │
# │      → Disparado por Cloud Scheduler a las 03:00 Europe/Madrid.         │
# │                                                                         │
# │   2) puntuador_horario  (Cloud Run **Service**)                         │
# │      → endpoint POST /run que lee BQ (últimos 60 min), computa armies + │
# │        gold y actualiza Firestore (user_balance + users + audit log).   │
# │      → Disparado por Cloud Scheduler al minuto 0 de cada hora.          │
# │                                                                         │
# │   3) BigQuery table `player_movements_raw` — destino de la pipeline de  │
# │      Noelia+Martha para los mensajes de player-movements.               │
# │                                                                         │
# │ Todo llega a estar ON sin intervención manual tras `terraform apply`.   │
# └─────────────────────────────────────────────────────────────────────────┘

# ─── BigQuery: tabla de pasos crudos (lo que escribe la pipeline) ────────────
resource "google_bigquery_table" "player_movements_raw" {
  dataset_id = google_bigquery_dataset.cloudrisk.dataset_id
  table_id   = "player_movements_raw"

  # Particionada por día → queries del último hora escanean 1 partición.
  time_partitioning {
    type  = "DAY"
    field = "ts"
  }
  # Clustering para acelerar "dame el jugador X en el último día"
  clustering = ["player_id", "source"]

  schema = jsonencode([
    { name = "ts",          type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "player_id",   type = "STRING",    mode = "REQUIRED" },
    { name = "steps_delta", type = "INT64",     mode = "REQUIRED" },
    { name = "latitude",    type = "FLOAT64",   mode = "NULLABLE" },
    { name = "longitude",   type = "FLOAT64",   mode = "NULLABLE" },
    { name = "speed_mps",   type = "FLOAT64",   mode = "NULLABLE" },
    { name = "source",      type = "STRING",    mode = "REQUIRED" }, # real|synthetic_walker|backend_sync
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])

  deletion_protection = false   # on purpose, low-risk analytics table
}

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

# ─── Cloud Run SERVICE: scorer horario ──────────────────────────────────────
resource "google_cloud_run_v2_service" "hourly_scorer" {
  name     = "cloudrisk-hourly-scorer"
  location = var.region
  # Cloud Scheduler llega con OIDC → no-allow-unauthenticated
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.steps_ingestor.email

    scaling {
      min_instance_count = 0   # escala a cero cuando no corre
      max_instance_count = 1   # no queremos concurrencia en el scorer
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk/steps-ingestor:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.cloudrisk.dataset_id
      }
      env {
        name  = "STEPS_TABLE"
        value = google_bigquery_table.player_movements_raw.table_id
      }
      env {
        name  = "SCORING_WINDOW_MIN"
        value = "60"
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.ingestor_bq_reader,
    google_project_iam_member.ingestor_bq_jobuser,
    google_project_iam_member.ingestor_firestore,
  ]
}

# El scheduler necesita poder invocar el scorer
resource "google_cloud_run_v2_service_iam_member" "scorer_scheduler_invoker" {
  project  = google_cloud_run_v2_service.hourly_scorer.project
  location = google_cloud_run_v2_service.hourly_scorer.location
  name     = google_cloud_run_v2_service.hourly_scorer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
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

# ─── Cloud Scheduler: scorer horario al minuto 0 ────────────────────────────
resource "google_cloud_scheduler_job" "hourly_scorer_cron" {
  name        = "cloudrisk-hourly-scorer-cron"
  region      = var.region
  description = "Lee BQ último hora, actualiza user_balance y users con armies+gold nuevos"
  schedule    = "0 * * * *"
  time_zone   = "Europe/Madrid"

  attempt_deadline = "120s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.hourly_scorer.uri}/run"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.hourly_scorer.uri
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.scorer_scheduler_invoker,
  ]
}

output "steps_fetcher_job_name" {
  value       = google_cloud_run_v2_job.steps_fetcher.name
  description = "Run-once-daily Cloud Run Job that ingests random_tracker data"
}

output "hourly_scorer_url" {
  value       = google_cloud_run_v2_service.hourly_scorer.uri
  description = "Scorer endpoint (POST /run). Invoked by Cloud Scheduler every hour."
}

output "player_movements_raw_table" {
  value       = "${var.project_id}.${google_bigquery_dataset.cloudrisk.dataset_id}.${google_bigquery_table.player_movements_raw.table_id}"
  description = "BQ table where Noelia+Martha's Dataflow writes all step events"
}
