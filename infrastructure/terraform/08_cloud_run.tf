# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 08_cloud_run.tf — Servicios y Jobs de Cloud Run                         │
# └─────────────────────────────────────────────────────────────────────────┘

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
    service_account = google_service_account.api.email

    containers {
      image = "${local.docker_registry}/api:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "USE_LOCAL_STORE"
        value = "0"
      }

      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.api_jwt_access,
    null_resource.image_api,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "api_scheduler" {
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# =============================================================================
# SERVICE 2: cloudrisk-web (frontend React)
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
          memory = "512Mi" # Mínimo requerido por Google con CPU siempre asignada
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [
    google_project_service.apis,
    null_resource.image_frontend,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# JOB 1: cloudrisk-air-ingestor (Alvaro — calidad_aire.py)
# =============================================================================
resource "google_cloud_run_v2_job" "air_ingestor" {
  name     = "cloudrisk-air-ingestor"
  location = var.region

  template {
    template {
      service_account = google_service_account.ingestor.email

      containers {
        image = "europe-west1-docker.pkg.dev/${var.project_id}/cloudrisk/air-ingestor:latest"
        
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
              secret  = "openweather-api-key"
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    null_resource.image_air_ingestor,
  ]
}

# =============================================================================
# JOB 2: cloudrisk-weather-ingestor (Alvaro — clima.py)
# =============================================================================
resource "google_cloud_run_v2_job" "weather_ingestor" {
  name     = "cloudrisk-weather-ingestor"
  location = var.region

  template {
    template {
      service_account = google_service_account.ingestor.email

      containers {
        image = "europe-west1-docker.pkg.dev/${var.project_id}/cloudrisk/weather-ingestor:latest"
        
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
              secret  = "openweather-api-key"
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    null_resource.image_weather_ingestor,
  ]
}

# =============================================================================
# JOB 3: cloudrisk-walker (Fran — bot que simula pasos)
# =============================================================================
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
            memory = "512Mi"
          }
        }
      }
      timeout = "600s"
    }
  }

  depends_on = [
    google_project_service.apis,
    null_resource.image_walker,
  ]
}