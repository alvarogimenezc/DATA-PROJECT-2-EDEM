# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 02_pubsub.tf — Topics y suscripciones de Pub/Sub                        │
# │                                                                         │
# │ Pub/Sub es el "cartero" entre servicios:                                │
# │   Productor --publica--> TOPIC --entrega--> SUBSCRIPCION <-- Consumidor │
# │                                                                         │
# │ En CloudRISK tenemos 3 canales, cada uno con su productor:              │
# │   1) player-movements  <- walker (bot de pasos, Fran)                   │
# │   2) air-quality       <- calidad_aire.py (ingestor, Alvaro)            │
# │   3) weather           <- clima.py (ingestor, Alvaro)                   │
# │                                                                         │
# │ Los 3 los consume Dataflow (Noelia + Martha) y escribe en BigQuery.     │
# │                                                                         │
# │ ¡IMPORTANTE! Los nombres de los 3 topics son el CONTRATO con el equipo  │
# │ de Alvaro (DATA-PROJECT-2-EDEM). No se renombran sin acuerdo.           │
# └─────────────────────────────────────────────────────────────────────────┘

# --------- TOPIC 1: player-movements ----------------------------------------
# Productor: juego_caminante.py (Cloud Run Job)
# Mensaje: {player_id, lat, lng, steps, timestamp}
resource "google_pubsub_topic" "player_movements" {
  name = "player-movements"

  # Labels para facturacion — te permite filtrar en el billing export
  labels = {
    owner     = "fran"
    component = "walker"
    contract  = "team"
  }

  depends_on = [google_project_service.apis]
}

# --------- TOPIC 2: air-quality ---------------------------------------------
# Productor: weather_airq/calidad_aire.py (Cloud Run Service)
# Mensaje: {zone_id, pm25, pm10, no2, multiplier, timestamp}
resource "google_pubsub_topic" "air_quality" {
  name = "air-quality"

  labels = {
    owner     = "alvaro"
    component = "ingestor-air"
    contract  = "team"
  }

  depends_on = [google_project_service.apis]
}

# --------- TOPIC 3: weather -------------------------------------------------
# Productor: weather_airq/clima.py (Cloud Run Service)
# Mensaje: {zone_id, temp_c, wind_kmh, main, multiplier, timestamp}
resource "google_pubsub_topic" "weather" {
  name = "weather"

  labels = {
    owner     = "alvaro"
    component = "ingestor-weather"
    contract  = "team"
  }

  depends_on = [google_project_service.apis]
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ SUSCRIPCIONES                                                           │
# │                                                                         │
# │ Un topic por si solo no entrega mensajes — los mensajes VIAJAN desde el │
# │ topic hasta cada SUSCRIPCION. Dataflow consume las 3 suscripciones.     │
# │                                                                         │
# │ Si pones `ack_deadline_seconds = 60`, Dataflow tiene 60s para procesar  │
# │ cada mensaje antes de que Pub/Sub asuma que fallo y lo reintente.       │
# └─────────────────────────────────────────────────────────────────────────┘

resource "google_pubsub_subscription" "player_movements_sub" {
  name                 = "player-movements-sub"
  topic                = google_pubsub_topic.player_movements.id
  ack_deadline_seconds = 60

  # expiration_policy vacia = la suscripcion NUNCA expira aunque no haya
  # consumidores. Util cuando la pipeline se para 1 dia — no pierdes la cola.
  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "air_quality_sub" {
  name                 = "air-quality-sub"
  topic                = google_pubsub_topic.air_quality.id
  ack_deadline_seconds = 60

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "weather_sub" {
  name                 = "weather-sub"
  topic                = google_pubsub_topic.weather.id
  ack_deadline_seconds = 60

  expiration_policy {
    ttl = ""
  }
}
