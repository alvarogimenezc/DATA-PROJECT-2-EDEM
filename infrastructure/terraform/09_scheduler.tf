# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 09_scheduler.tf — Cloud Scheduler (cron serverless)                     │
# │                                                                         │
# │ Cloud Scheduler lanza llamadas HTTP en un cron, sin servidores. Lo      │
# │ usamos para:                                                            │
# │   1) Decay diario: reducir poder de los jugadores un 15% cada dia       │
# │      (asi el leaderboard no se queda estatico).                         │
# │   2) Auto-resolver batallas expiradas cada hora.                        │
# │                                                                         │
# │ El Scheduler llama al backend con un token OIDC — el backend solo       │
# │ acepta peticiones firmadas por el SA `cloudrisk-scheduler` (ver         │
# │ 08_cloud_run.tf -> api_scheduler binding).                              │
# │                                                                         │
# │ Coste: 3 jobs gratis/mes, luego 0.10$ por job. Con 2 jobs estamos       │
# │ dentro del free tier siempre.                                           │
# └─────────────────────────────────────────────────────────────────────────┘

# --------- JOB 1: Power decay diario --------------------------------------
# Cron "0 3 * * *" = cada dia a las 03:00 Europe/Madrid (hora local)
resource "google_cloud_scheduler_job" "power_decay" {
  name        = "cloudrisk-power-decay"
  description = "Aplica 15% de decay diario al poder de los jugadores"
  schedule    = "0 3 * * *"
  time_zone   = "Europe/Madrid"

  # Si el API no responde en 60s se considera fallida y se reintenta
  attempt_deadline = "60s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/v1/users/decay"

    # OIDC firma la peticion con el SA del scheduler. El API comprueba
    # que el JWT es valido Y que el issuer es google.
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.api.uri
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_service_iam_member.api_scheduler,
  ]
}

# --------- JOB 2: Auto-resolver batallas cada hora ------------------------
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

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.api.uri
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_service_iam_member.api_scheduler,
  ]
}
