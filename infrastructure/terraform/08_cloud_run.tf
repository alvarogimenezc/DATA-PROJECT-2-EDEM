# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 08_cloud_run.tf — Servicios y Jobs de Cloud Run                         │
# │                                                                         │
# │ Cloud Run corre contenedores Docker con 2 modos:                        │
# │                                                                         │
# │   SERVICE: stateless HTTP, escala a cero, responde peticiones.          │
# │            -> backend, frontend, ingestors                              │
# │                                                                         │
# │   JOB:     batch one-shot o cron, no recibe HTTP, corre y muere.        │
# │            -> walker (simula pasos y publica a Pub/Sub)                 │
# │                                                                         │
# │ Analogia:                                                               │
# │   - SERVICE = tienda siempre abierta (abre solo cuando entra cliente)   │
# │   - JOB     = repartidor que hace un pedido y se va a casa              │
# └─────────────────────────────────────────────────────────────────────────┘

# --------- Atajo: la URL base del registry Docker de este proyecto ----------
locals {
  docker_registry = "${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk"
}

# =============================================================================
# SERVICE 1: cloudrisk-api (backend FastAPI)
# =============================================================================
resource "google_cloud_run_v2_service" "api" {
  name     = "cloudrisk-api"
  location = var.region

  template {
    # El backend corre con el SA de la API — asi tiene los permisos de 07_iam
    service_account = google_service_account.api.email

    containers {
      image = "${local.docker_registry}/api:latest"

      # --- Variables de entorno simples ---
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "USE_LOCAL_STORE"
        value = "0" # en prod usamos Firestore real, no in-memory
      }

      # --- Variable de entorno desde Secret Manager ---
      # Cloud Run lee el secreto y lo expone como SECRET_KEY al proceso.
      # El SA "api" tiene el rol secretAccessor sobre este secreto (ver 07_iam).
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      # Limites de recursos — 1 vCPU + 512MB = suficiente para FastAPI
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0  # escala a cero cuando nadie usa
      max_instance_count = 10 # proteccion contra DDoS (y contra facturas)
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.api_jwt_access,
  ]
}

# Dejamos el API publico — es una API publica de juego, no hay login en el
# nivel de Cloud Run (el login lo hace el backend con JWT).
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Permitir que el Scheduler invoque el API (para los cron jobs)
resource "google_cloud_run_v2_service_iam_member" "api_scheduler" {
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# =============================================================================
# SERVICE 2: cloudrisk-web (frontend React + MapLibre 3D)
# =============================================================================
resource "google_cloud_run_v2_service" "web" {
  name     = "cloudrisk-web"
  location = var.region

  template {
    containers {
      image = "${local.docker_registry}/frontend:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi" # frontend estatico — 256MB sobran
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# NOTA: el antiguo servicio Streamlit `cloudrisk-dashboard` se eliminó al
# consolidar la analítica en el frontend React (endpoints /analytics/* del
# backend FastAPI sobre BigQuery).
# =============================================================================

# =============================================================================
# SERVICE 4: cloudrisk-air-ingestor (Alvaro — calidad_aire.py)
# =============================================================================
# min_instances = 1 porque necesita un loop continuo de polling a OWM.
# Si escalara a cero dejaria de pollear cada 30s.
resource "google_cloud_run_v2_service" "air_ingestor" {
  name     = "cloudrisk-air-ingestor"
  location = var.region

  template {
    service_account = google_service_account.ingestor.email

    containers {
      image = "${local.docker_registry}/air-ingestor:latest"

      env {
        name  = "PUBSUB_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_AIR"
        value = google_pubsub_topic.air_quality.name
      }
      env {
        name = "OPENWEATHER_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.owm_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }
    }

    scaling {
      min_instance_count = 1 # siempre una corriendo (polling loop)
      max_instance_count = 1 # nunca mas de 1 — no paralelizamos
    }
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# SERVICE 5: cloudrisk-weather-ingestor (Alvaro — clima.py)
# =============================================================================
resource "google_cloud_run_v2_service" "weather_ingestor" {
  name     = "cloudrisk-weather-ingestor"
  location = var.region

  template {
    service_account = google_service_account.ingestor.email

    containers {
      image = "${local.docker_registry}/weather-ingestor:latest"

      env {
        name  = "PUBSUB_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_WEATHER"
        value = google_pubsub_topic.weather.name
      }
      env {
        name = "OPENWEATHER_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.owm_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# JOB 1: cloudrisk-walker (Fran — bot que simula pasos)
# =============================================================================
# Un JOB != SERVICE: NO tiene URL ni recibe HTTP. Se ejecuta con
# `gcloud run jobs execute cloudrisk-walker --region=europe-west1` o con
# un trigger de Cloud Scheduler.
resource "google_cloud_run_v2_job" "walker" {
  name     = "cloudrisk-walker"
  location = var.region

  template {
    template {
      service_account = google_service_account.walker.email

      containers {
        image = "${local.docker_registry}/walker:latest"

        env {
          name  = "PUBSUB_PROJECT"
          value = var.project_id
        }
        env {
          name  = "PUBSUB_TOPIC_PLAYER"
          value = google_pubsub_topic.player_movements.name
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }
      }

      # Max 10 minutos por ejecucion del job
      timeout = "600s"
    }
  }

  depends_on = [google_project_service.apis]
}
