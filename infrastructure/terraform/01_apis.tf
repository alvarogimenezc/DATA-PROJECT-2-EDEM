# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 01_apis.tf — Habilitar las APIs de GCP que vamos a usar                │
# │                                                                         │
# │ Un proyecto GCP viene "apagado": puedes verlo pero no puedes crear      │
# │ NADA hasta que habilitas la API de cada servicio. Equivalente en la    │
# │ consola: Menu > APIs y servicios > Habilitar.                          │
# │                                                                         │
# │ Lo hacemos con un for_each sobre una lista para:                        │
# │   1) No repetir el mismo recurso 10 veces                               │
# │   2) Poder anadir/quitar APIs cambiando UNA linea                       │
# │                                                                         │
# │ Analogia: GCP es un supermercado y cada API es un departamento.         │
# │ Tienes que "encender las luces" del departamento antes de poder comprar.│
# └─────────────────────────────────────────────────────────────────────────┘

# toset() convierte una lista en un "set" (sin duplicados) que for_each puede
# iterar. Cada clave del set crea un recurso distinto.
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",              # Cloud Run (services + jobs)
    "firestore.googleapis.com",         # Firestore (BD NoSQL)
    "pubsub.googleapis.com",            # Pub/Sub (cola de mensajes)
    "bigquery.googleapis.com",          # BigQuery (data warehouse)
    "secretmanager.googleapis.com",     # Secret Manager (secretos cifrados)
    "artifactregistry.googleapis.com",  # Artifact Registry (Docker registry)
    "cloudbuild.googleapis.com",        # Cloud Build (CI/CD)
    "dataflow.googleapis.com",          # Dataflow (Beam streaming)
    "iam.googleapis.com",               # IAM (permisos)
    "cloudscheduler.googleapis.com",    # Cron jobs serverless
    "eventarc.googleapis.com",          # Eventos entre servicios
    "logging.googleapis.com",           # Logs centralizados
  ])

  service = each.key

  # disable_on_destroy = false evita que un `terraform destroy` apague APIs
  # que puedan estar en uso por OTROS recursos no gestionados por nosotros.
  # Es una red de seguridad. En clase siempre = false.
  disable_on_destroy = false
}
