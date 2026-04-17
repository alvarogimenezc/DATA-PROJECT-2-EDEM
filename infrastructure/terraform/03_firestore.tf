# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 03_firestore.tf — Base de datos NoSQL operativa                         │
# │                                                                         │
# │ Firestore es la BD "en caliente" del juego:                             │
# │   - users         -> 4 comandantes + sus stats                          │
# │   - zones         -> 87 barrios de Valencia (geojson)                   │
# │   - user_balance  -> CONTRATO con el equipo: armies + steps por jugador │
# │   - location_balance -> CONTRATO: armies + owner por zona               │
# │                                                                         │
# │ Por que Firestore y no Postgres? Porque escala a cero, es NoSQL simple  │
# │ con indices automaticos, y el free tier aguanta nuestros 10 usuarios    │
# │ concurrentes sin coste.                                                 │
# │                                                                         │
# │ Analogia: Firestore es un "Google Docs" para JSONs — escritura          │
# │ concurrente sin bloquear, sin migraciones de schema, pago por lectura.  │
# └─────────────────────────────────────────────────────────────────────────┘

resource "google_firestore_database" "cloudrisk" {
  # name = "(default)" crea el database PRIMARIO. Es el unico que puede
  # leerse con `firestore.Client()` sin especificar nombre — util para que
  # todo el equipo apunte al mismo sin codigo distinto por persona.
  name = "(default)"

  # Multi-region EUR3 (Belgica + Paises Bajos + Finlandia) para HA real.
  # Para dev un single-region (europe-west1) basta y es mas barato.
  location_id = "eur3"

  # FIRESTORE_NATIVE: API moderna, lo que usamos.
  # (El otro modo, DATASTORE_MODE, es el legacy de App Engine — nunca.)
  type = "FIRESTORE_NATIVE"

  # Protege contra borrado accidental. Para destruir el database hay que
  # poner este flag en "DELETE_PROTECTION_DISABLED" primero. Lifesaver.
  delete_protection_state = "DELETE_PROTECTION_ENABLED"

  # PITR (Point-in-Time Recovery): guarda snapshots de los ultimos 7 dias.
  # Si un bug borra documentos, podemos hacer time-travel al estado de
  # "hace 3 horas". Cuesta ~0.01 EUR/mes con nuestros 200KB de datos.
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"

  depends_on = [google_project_service.apis]
}

# NOTA: los DOCUMENTOS (datos) NO se crean con Terraform — los creamos con
# `python scripts/sembrar_firestore.py` despues del apply. Terraform es para
# infraestructura, no para datos.
