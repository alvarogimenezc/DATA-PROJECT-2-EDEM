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
    env     = "prod"
    course  = "serverless-edem-2026"
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
    { name = "ts",            type = "TIMESTAMP", mode = "REQUIRED", description = "Cuando la medida fue tomada" },
    { name = "type",          type = "STRING",    mode = "REQUIRED", description = "air_quality | weather" },
    { name = "multiplier",    type = "FLOAT",     mode = "REQUIRED", description = "Multiplicador del juego [0.6, 1.5]" },
    { name = "raw_payload",   type = "STRING",    mode = "REQUIRED", description = "JSON original del ingestor" },
    { name = "processed_at",  type = "TIMESTAMP", mode = "REQUIRED", description = "Cuando Dataflow proceso la fila" },
  ])
}
