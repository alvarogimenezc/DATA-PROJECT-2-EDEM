# ┌─────────────────────────────────────────────────────────────────────────┐
# │ outputs.tf — Valores que Terraform imprime al terminar                  │
# │                                                                         │
# │ Los outputs aparecen DESPUES de `terraform apply`:                      │
# │   api_url = "https://cloudrisk-api-xxxxx.europe-west1.run.app"          │
# │   web_url = "https://cloudrisk-web-xxxxx.europe-west1.run.app"          │
# │                                                                         │
# │ Los usamos para:                                                        │
# │   1) Saber las URLs sin entrar a la consola                             │
# │   2) Consumirlos desde scripts (terraform output -raw api_url)          │
# │   3) Validar automaticamente en el pipeline CI/CD                       │
# └─────────────────────────────────────────────────────────────────────────┘

output "api_url" {
  description = "URL publica del backend FastAPI"
  value       = google_cloud_run_v2_service.api.uri
}

output "web_url" {
  description = "URL publica del frontend React"
  value       = google_cloud_run_v2_service.web.uri
}

output "dashboard_url" {
  description = "URL publica del dashboard Streamlit"
  value       = google_cloud_run_v2_service.dashboard.uri
}

output "artifact_registry" {
  description = "Prefijo del registry para empujar imagenes Docker"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/cloudrisk"
}

output "firestore_database" {
  description = "Nombre del database Firestore (siempre '(default)')"
  value       = google_firestore_database.cloudrisk.name
}

output "bigquery_dataset" {
  description = "Dataset BigQuery para analytics"
  value       = "${var.project_id}.${google_bigquery_dataset.cloudrisk.dataset_id}"
}

output "pubsub_topics" {
  description = "Los 3 topics Pub/Sub del contrato con el equipo"
  value = {
    player_movements = google_pubsub_topic.player_movements.name
    air_quality      = google_pubsub_topic.air_quality.name
    weather          = google_pubsub_topic.weather.name
  }
}
