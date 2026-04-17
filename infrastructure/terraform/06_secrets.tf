# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 06_secrets.tf — Secret Manager                                          │
# │                                                                         │
# │ NUNCA pongas secretos en:                                               │
# │   - Codigo fuente                                                       │
# │   - Variables de entorno en el Dockerfile                               │
# │   - Variables de entorno en el Cloud Run (visibles en la consola)       │
# │                                                                         │
# │ Los metes en Secret Manager. Cloud Run los lee en runtime via IAM.      │
# │ Cada secreto tiene VERSIONES — puedes rotarlo sin downtime.             │
# │                                                                         │
# │ Nosotros manejamos 2 secretos:                                          │
# │   1) cloudrisk-jwt-secret   -> firma tokens JWT del backend             │
# │   2) openweather-api-key    -> clave para llamar a OpenWeatherMap       │
# │                                                                         │
# │ Coste: 0.06$ por secreto al mes. Despreciable.                          │
# └─────────────────────────────────────────────────────────────────────────┘

# --------- SECRET 1: JWT secret del backend --------------------------------
resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "cloudrisk-jwt-secret"

  # `replication.auto {}` = Google replica el secreto globalmente por ti.
  # No te preocupas de donde vive fisicamente.
  replication {
    auto {}
  }

  labels = {
    app   = "cloudrisk"
    owner = "fran"
  }

  depends_on = [google_project_service.apis]
}

# La "version 1" del secreto — el valor actual. Cuando quieras rotarlo, en
# vez de borrar esta version creas una version 2:
#   gcloud secrets versions add cloudrisk-jwt-secret --data-file=- <<< "nuevo"
resource "google_secret_manager_secret_version" "jwt_secret_v1" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = var.jwt_secret # viene de terraform.tfvars
}

# --------- SECRET 2: OpenWeatherMap API key --------------------------------
# Este secreto lo crea Terraform pero el VALOR lo metes a mano con:
#   gcloud secrets versions add openweather-api-key --data-file=- <<< "TU_KEY"
# (porque OWM requiere registro humano y no queremos la key en tfvars)
resource "google_secret_manager_secret" "owm_api_key" {
  secret_id = "openweather-api-key"

  replication {
    auto {}
  }

  labels = {
    app   = "cloudrisk"
    owner = "alvaro"
  }

  depends_on = [google_project_service.apis]
}
