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

# La base de datos Firestore (default) la crea GCP automáticamente al
# activar la API y no puede eliminarse — no se gestiona con Terraform.

# NOTA: los DOCUMENTOS (datos) NO se crean con Terraform — los creamos con
# `python scripts/sembrar_firestore.py` despues del apply. Terraform es para
# infraestructura, no para datos.
