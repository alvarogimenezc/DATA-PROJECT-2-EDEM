# `steps_ingestor/` — Ingesta diaria de pasos reales

**Dueño:** Álvaro (extensión del work de `weather_airq/`).
**Contrato del equipo:** publica en el topic `player-movements` con `source="real"` — el mismo topic que consume el pipeline unificado de Dataflow.

> **Cambio 2026-04:** antes había dos componentes aquí —
> `recolector_pasos_diario.py` + `puntuador_horario.py` (Cloud Run horario
> que leía BQ y escribía Firestore). **El scoring se ha movido al pipeline
> unificado `pipelines/cloudrisk_unified.py`**, que lo hace en streaming
> con estado por jugador. Este módulo se queda sólo con la *ingesta* de
> pasos; el Cloud Run scorer y su Scheduler ya no existen.

---

## Qué hace ahora

Una sola responsabilidad: pull diario del tracker de GitHub → Pub/Sub.

### `recolector_pasos_diario.py` — Cloud Run Job, corre **1 vez al día**

1. Descarga el JSON más reciente de
   [`github.com/FranciscoAlvarezVaras/random_tracker`](https://github.com/FranciscoAlvarezVaras/random_tracker)
   usando `raw.githubusercontent.com` (no hace falta token — es público).
2. Deduplica contra `step_logs/` en Firestore (evita reprocesar si se relanza).
3. Por cada entry `{timestamp, latitude, longitude}` publica a Pub/Sub
   `player-movements` con schema:

   ```json
   {
     "player_id": "demo-player-001",
     "timestamp": "2026-04-16T08:12:34Z",
     "latitude": 39.4702,
     "longitude": -0.3768,
     "speed_mps": 1.4,
     "steps_delta": 1250,
     "source": "real"
   }
   ```

4. Escribe un marker `step_ingests/{date}` para idempotencia diaria.

A partir de aquí el pipeline de Dataflow (`cloudrisk_unified.py`) recoge el
mensaje, aplica anti-trampa + multiplicador ambiental, y escribe a
Firestore (`user_balance/`, `users/`) y BigQuery (`player_scoring_events`).

---

## Flujo end-to-end

```
      ┌───────────────────────────────────────┐
      │  github.com/FranciscoAlvarezVaras     │
      │       /random_tracker (JSON)          │
      └──────────────┬────────────────────────┘
                     │  HTTPS GET, 1×/día a las 03:00 UTC
                     ▼
    ┌───────────────────────────────┐
    │  recolector_pasos_diario.py   │   Cloud Run Job (scheduled)
    │  (steps_ingestor/)            │
    └──────────┬────────────────────┘
               │  publish N mensajes
               ▼
        ┌──────────────────┐
        │  Pub/Sub topic   │
        │  player-movements│
        └────────┬─────────┘
                 │
                 ▼
      ┌────────────────────────────────┐
      │  pipelines/cloudrisk_unified   │   Dataflow streaming (stateful)
      │  — anti-trampa + scoring       │
      └──────┬───────────────────┬─────┘
             ▼                   ▼
       Firestore             BigQuery
       user_balance/         player_scoring_events
       (armies, gold)        (histórico + DLQ)
```

El scorer horario que existía antes (`puntuador_horario.py`) ha desaparecido:
su lógica vive en el `StatefulScoringDoFn` del pipeline unificado y corre
**en streaming** (por-evento) en vez de batch horario.

---

## Añadir un nuevo usuario al tracker

1. Fran da de alta al usuario en Firestore `users/` (nombre, email, clan_color).
2. En `data/random_tracker_mapping.json` mapear
   `{"filename_pattern_in_repo": "demo-player-001"}`.
3. El fetcher lee ese mapping cada run — sin redeploy.

---

## Deploy

```bash
# Cloud Run Job (daily)
cd steps_ingestor
gcloud run jobs deploy cloudrisk-steps-fetcher \
  --source=. \
  --region=europe-west1 \
  --tasks=1 \
  --set-env-vars=PROJECT_ID=$PROJECT_ID,TRACKER_REPO=FranciscoAlvarezVaras/random_tracker

# Cloud Scheduler que lo invoca a las 03:00 UTC
gcloud scheduler jobs create http cloudrisk-steps-fetcher-daily \
  --location=europe-west1 \
  --schedule='0 3 * * *' \
  --time-zone=Europe/Madrid \
  --uri=https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/cloudrisk-steps-fetcher:run \
  --http-method=POST \
  --oauth-service-account-email=cloudrisk-scheduler@$PROJECT_ID.iam.gserviceaccount.com
```

Terraform lo cablea solo en `infrastructure/terraform/09_scheduler.tf`.
El recurso del Cloud Run *hourly scorer* y su Scheduler cron fueron
**eliminados** en el refactor de abril 2026.

---

## Simulación local (sin tocar GitHub real)

```bash
# Datos de prueba falsos
export TRACKER_REPO=local
export TRACKER_LOCAL_PATH=./data/mock_tracker_feed.json

# Fetcher contra el emulator
FIRESTORE_EMULATOR_HOST=localhost:8200 \
PUBSUB_EMULATOR_HOST=localhost:8085 \
python recolector_pasos_diario.py --project cloudrisk-local --date 2026-04-16
```

---

## Tests

`pytest tests/` ejecuta:
- `test_fetcher_parses_github_json` (con HTTP mocked)
- `test_dedup_same_day_twice`

El test `test_scorer_applies_multipliers` ya no aplica aquí — la misma
funcionalidad se cubre ahora en `tests/pipelines/test_cloudrisk_unified.py`.


# 📥 Módulo de Ingesta de Pasos (`steps_ingestor/`)

Este módulo se encarga de simular la conexión de nuestra app con dispositivos reales (como relojes inteligentes o Strava). Para no tener que salir a andar de verdad, descargamos datos de movimiento desde un repositorio de GitHub y los metemos en nuestro sistema Cloud.

## ¿Qué hace exactamente?

El script principal `recolector_pasos_diario.py` se ejecuta **1 vez al día**:

1. Descarga el archivo JSON más reciente desde el repositorio de rutas aleatorias.
2. Comprueba en Firestore si ya hemos procesado esos datos hoy (para no duplicar puntos).
3. Transforma los datos y los envía a nuestro topic principal en **Pub/Sub** (`player-movements`).

Una vez en Pub/Sub, nuestro pipeline de **Dataflow** recoge estos pasos, aplica las matemáticas del juego (clima y aire) y actualiza el saldo del jugador en la base de datos.

## 🚀 Cómo probarlo localmente

Si quieres ver cómo el script lee el archivo y simula el envío sin gastar saldo en Google Cloud, usa el parámetro `--dry-run`:

```bash
export PROJECT_ID=cloudrisk-492619
python recolector_pasos_diario.py --project $PROJECT_ID --dry-run