# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 09_scheduler.tf — Cloud Scheduler (cron serverless)                     │
# │                                                                         │
# │ Cloud Scheduler lanza llamadas HTTP en un cron, sin servidores. Lo      │
# │ usamos para:                                                            │
# │   1) Auto-resolver batallas expiradas cada hora.                        │
# │                                                                         │
# │ El backend valida el header X-Scheduler-Token comparándolo contra       │
# │ settings.SCHEDULER_SECRET (leído desde Secret Manager). OIDC no es      │
# │ necesario porque el servicio Cloud Run es público (allUsers).           │
# │                                                                         │
# │ Coste: 3 jobs gratis/mes, luego 0.10$ por job. Con 1 job estamos        │
# │ siempre dentro del free tier.                                           │
# └─────────────────────────────────────────────────────────────────────────┘

# --------- JOB: Auto-resolver batallas cada hora --------------------------
# Cron "0 * * * *" = al minuto 0 de cada hora
resource "google_cloud_scheduler_job" "resolve_battles" {
  name        = "cloudrisk-resolve-battles"
  description = "Auto-resuelve batallas cuya deadline ha pasado"
  schedule    = "0 * * * *"
  time_zone   = "Europe/Madrid"

  attempt_deadline = "60s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/v1/battles/resolve-expired"

    # Header que el backend compara con settings.SCHEDULER_SECRET. Ver
    # backend/cloudrisk_api/endpoints/batallas.py::resolve_expired_battles.
    headers = {
      "X-Scheduler-Token" = var.scheduler_secret
    }
  }

  depends_on = [
    google_project_service.apis,
  ]
}
