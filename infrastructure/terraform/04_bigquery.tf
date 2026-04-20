# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 04_bigquery.tf — Data Warehouse analitico                               │
# │                                                                         │
# │ BigQuery es lo contrario a Firestore:                                   │
# │   - Firestore: rapido para 1 registro, lento para 1.000.000             │
# │   - BigQuery : lento para 1 registro, rapido para 1.000.000.000         │
# │                                                                         │
# │ Lo usamos para:                                                         │
# │   1) environmental_factors  <- aqui escribe Dataflow                    │
# │   2) user_actions           <- historico de movimientos                 │
# │   3) daily_rollup           <- vistas agregadas                         │
# │                                                                         │
# │ Coste: 1 TB de queries/mes GRATIS, despues 5$/TB. Con 10 partidas/dia   │
# │ hacemos unos 100 MB/mes — siempre dentro del free tier.                 │
# │                                                                         │
# │ Analogia: BigQuery es Excel con 1.000M de filas y SQL nativo.           │
# └─────────────────────────────────────────────────────────────────────────┘

# Dataset = namespace. Dentro viven las tablas.
resource "google_bigquery_dataset" "cloudrisk" {
  dataset_id = "cloudrisk"
  location   = "EU" # Multi-region EU (no europe-west1) — mas tolerante a fallos

  # Descripcion se ve en la consola. Util cuando el profesor mira tu proyecto.
  description = "CloudRISK analytics dataset — environmental factors, user actions, rollups"

  # Cualquiera con el rol bigquery.dataViewer puede leer. Mantenemos las
  # writes limitadas al SA de la API y al SA de Dataflow (ver 07_iam.tf).
  delete_contents_on_destroy = false # Protege contra `terraform destroy`

  labels = {
    env      = "prod"
    course   = "serverless-edem-2026"
    contract = "team"
  }

  depends_on = [google_project_service.apis]
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ TABLA environmental_factors                                             │
# │                                                                         │
# │ Aqui escribe el pipeline Dataflow (Noelia + Martha). Cada mensaje de    │
# │ air-quality o weather genera 1 fila.                                    │
# │                                                                         │
# │ Definimos el schema aqui para que:                                      │
# │   1) Terraform cree la tabla con las columnas correctas                 │
# │   2) Dataflow no tenga que "adivinarlas" en cada insert                 │
# │                                                                         │
# │ `time_partitioning`: BigQuery parte la tabla por dia. Cuando consultas  │
# │ `WHERE ts >= '2026-04-16'`, solo escanea el particion de ese dia =>     │
# │ mas rapido y mas barato.                                                │
# └─────────────────────────────────────────────────────────────────────────┘
resource "google_bigquery_table" "environmental_factors" {
  dataset_id = google_bigquery_dataset.cloudrisk.dataset_id
  table_id   = "environmental_factors"

  deletion_protection = true # No se puede borrar accidentalmente

  time_partitioning {
    type  = "DAY"
    field = "ts"
  }

  schema = jsonencode([
    { name = "ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Cuando la medida fue tomada" },
    { name = "type", type = "STRING", mode = "REQUIRED", description = "air_quality | weather" },
    { name = "multiplier", type = "FLOAT", mode = "REQUIRED", description = "Multiplicador del juego [0.6, 1.5]" },
    { name = "raw_payload", type = "STRING", mode = "REQUIRED", description = "JSON original del ingestor" },
    { name = "processed_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Cuando Dataflow proceso la fila" },
  ])
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ TABLA player_scoring_events                                             │
# │                                                                         │
# │ La escribe el stateful DoFn del pipeline unificado por cada evento de   │
# │ pasos procesado. Incluye velocidad, distancia, multiplicador aplicado,  │
# │ ejércitos ganados y si tocó el cap diario.                              │
# └─────────────────────────────────────────────────────────────────────────┘
resource "google_bigquery_table" "player_scoring_events" {
  dataset_id = google_bigquery_dataset.cloudrisk.dataset_id
  table_id   = "player_scoring_events"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "ts"
  }
  clustering = ["player_id"]

  schema = jsonencode([
    { name = "player_id", type = "STRING", mode = "REQUIRED" },
    { name = "ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "latitude", type = "FLOAT", mode = "NULLABLE" },
    { name = "longitude", type = "FLOAT", mode = "NULLABLE" },
    { name = "steps_delta", type = "INTEGER", mode = "REQUIRED" },
    { name = "distance_m", type = "FLOAT", mode = "REQUIRED" },
    { name = "speed_kmh", type = "FLOAT", mode = "REQUIRED" },
    { name = "env_multiplier", type = "FLOAT", mode = "REQUIRED" },
    { name = "rappel_applied", type = "BOOLEAN", mode = "REQUIRED" },
    { name = "armies_earned", type = "INTEGER", mode = "REQUIRED" },
    { name = "armies_today_after", type = "INTEGER", mode = "REQUIRED" },
    { name = "capped", type = "BOOLEAN", mode = "REQUIRED" },
    { name = "processed_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ TABLA dead_letter                                                       │
# │                                                                         │
# │ Mensajes rechazados por el pipeline: JSON inválido, campos faltantes o  │
# │ velocidad > MAX_SPEED_KMH (anti-trampa). Útil para auditar y depurar.   │
# └─────────────────────────────────────────────────────────────────────────┘
resource "google_bigquery_table" "dead_letter" {
  dataset_id = google_bigquery_dataset.cloudrisk.dataset_id
  table_id   = "dead_letter"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "processed_at"
  }

  schema = jsonencode([
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "reason", type = "STRING", mode = "REQUIRED" },
    { name = "player_id", type = "STRING", mode = "NULLABLE" },
    { name = "raw_payload", type = "STRING", mode = "REQUIRED" },
    { name = "processed_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}
