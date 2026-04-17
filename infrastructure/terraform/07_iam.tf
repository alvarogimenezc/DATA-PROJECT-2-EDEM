# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 07_iam.tf — Service Accounts + permisos (IAM)                           │
# │                                                                         │
# │ Regla de oro de seguridad en GCP: "least privilege".                    │
# │ Un servicio SOLO tiene los permisos que NECESITA. Nunca mas.            │
# │                                                                         │
# │ Cada servicio corre con su propio Service Account (SA):                 │
# │   - cloudrisk-api         -> Firestore rw, Pub/Sub publish, BQ insert   │
# │   - cloudrisk-scheduler   -> llamar al API cada hora                    │
# │   - cloudrisk-dataflow    -> Pub/Sub subscribe, BQ insert               │
# │                                                                         │
# │ Analogia: cada servicio es un empleado con su propia tarjeta de         │
# │ identificacion. La tarjeta solo abre las puertas que ese empleado       │
# │ necesita. Si te roban la tarjeta del conserje, no accedes al despacho   │
# │ del CEO.                                                                │
# └─────────────────────────────────────────────────────────────────────────┘

# =============================================================================
# SERVICE ACCOUNT 1: cloudrisk-api (lo usa el backend FastAPI)
# =============================================================================
resource "google_service_account" "api" {
  account_id   = "cloudrisk-api"
  display_name = "CloudRISK API Service Account"
  description  = "SA del backend FastAPI que corre en Cloud Run"
  depends_on   = [google_project_service.apis]
}

# --- Permisos del SA de la API ---
# locals crea un "atajo" reutilizable — evitamos copiar el email del SA
# cada vez que necesitamos asignarle un rol.
locals {
  api_sa_member = "serviceAccount:${google_service_account.api.email}"
}

# Leer/escribir documentos en Firestore
resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = local.api_sa_member
}

# Publicar mensajes en los 3 topics Pub/Sub
resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = local.api_sa_member
}

# Insertar datos en BigQuery (streaming inserts para step_logs)
resource "google_project_iam_member" "api_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = local.api_sa_member
}

# Correr queries en BigQuery (necesario ademas del dataEditor)
resource "google_project_iam_member" "api_bigquery_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.api_sa_member
}

# Leer el JWT secret en runtime — permiso SOBRE UN SECRETO ESPECIFICO,
# no a nivel de proyecto. Mas restrictivo = mas seguro.
resource "google_secret_manager_secret_iam_member" "api_jwt_access" {
  secret_id = google_secret_manager_secret.jwt_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.api_sa_member
}

# =============================================================================
# SERVICE ACCOUNT 2: cloudrisk-scheduler (para los cron jobs de Cloud Scheduler)
# =============================================================================
resource "google_service_account" "scheduler" {
  account_id   = "cloudrisk-scheduler"
  display_name = "CloudRISK Cloud Scheduler"
  description  = "SA que usan los cron jobs para llamar al API"
  depends_on   = [google_project_service.apis]
}

# El SA del Scheduler solo necesita PODER LLAMAR al servicio API.
# Nada mas. Le damos roles/run.invoker solo en ese servicio (ver 08_cloud_run.tf).
# El binding esta alli para que el fichero 07 solo tenga "quien es quien".

# =============================================================================
# SERVICE ACCOUNT 3: cloudrisk-ingestors (Alvaro — calidad_aire.py, clima.py)
# =============================================================================
resource "google_service_account" "ingestor" {
  account_id   = "cloudrisk-ingestor"
  display_name = "CloudRISK Ingestors"
  description  = "SA de los ingestors air-quality y weather"
  depends_on   = [google_project_service.apis]
}

locals {
  ingestor_sa_member = "serviceAccount:${google_service_account.ingestor.email}"
}

# Publicar en Pub/Sub (solo los 2 topics de ingestion)
resource "google_pubsub_topic_iam_member" "ingestor_publish_air" {
  topic  = google_pubsub_topic.air_quality.name
  role   = "roles/pubsub.publisher"
  member = local.ingestor_sa_member
}

resource "google_pubsub_topic_iam_member" "ingestor_publish_weather" {
  topic  = google_pubsub_topic.weather.name
  role   = "roles/pubsub.publisher"
  member = local.ingestor_sa_member
}

# Leer la OpenWeatherMap API key
resource "google_secret_manager_secret_iam_member" "ingestor_owm_access" {
  secret_id = google_secret_manager_secret.owm_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.ingestor_sa_member
}

# =============================================================================
# SERVICE ACCOUNT 4: cloudrisk-walker (Fran — Cloud Run Job)
# =============================================================================
resource "google_service_account" "walker" {
  account_id   = "cloudrisk-walker"
  display_name = "CloudRISK Walker Job"
  description  = "SA del bot que simula los pasos de los jugadores"
  depends_on   = [google_project_service.apis]
}

resource "google_pubsub_topic_iam_member" "walker_publish" {
  topic  = google_pubsub_topic.player_movements.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.walker.email}"
}
