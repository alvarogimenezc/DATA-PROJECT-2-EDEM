# `steps_ingestor/` — Ingesta diaria de pasos reales + scoring horario

**Dueño:** Álvaro (extensión del work de `weather_airq/`).
**Contrato del equipo:** publica en el topic `player-movements` con `source="real"` — mismo topic que ya consume la pipeline de Noelia+Martha.

---

## Qué hace

Dos componentes, cada uno con responsabilidad única:

### 1. `recolector_pasos_diario.py` — Cloud Run Job, corre **1 vez al día**

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

### 2. `puntuador_horario.py` — Cloud Run Service, trigger Cloud Scheduler cada hora

1. Consulta BigQuery `cloudrisk.player_movements_raw` (últimos 60 min).
2. Suma pasos por `player_id` y aplica el multiplicador ambiental de BQ
   (`environmental_factors` de la pipeline de Noelia+Martha).
3. Calcula puntos nuevos: `puntos = pasos * multiplicador_aire * multiplicador_tiempo`.
4. Actualiza `user_balance/{player_id}`:
   - `total_steps += pasos_última_hora`
   - `armies += puntos / 10`  (1 army por cada 10 puntos)
   - `gold += puntos / 100`   (1 gold por cada 100 puntos)
   - `updated_at = now()`

Resultado: los jugadores despiertan cada mañana con sus pasos del día
anterior ya convertidos en armies y gold listos para usar.

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
    │  recolector_pasos_diario          │   Cloud Run Job (scheduled)
    │  (steps_ingestor/)            │
    └──────────┬────────────────────┘
               │  publish N mensajes
               ▼
        ┌──────────────────┐
        │  Pub/Sub topic   │
        │  player-movements│
        └─────┬────────────┘
              │
     ┌────────┴─────────┐
     ▼                  ▼
  Dataflow pipeline    puntuador_horario (Cloud Run)
  (Noelia+Martha)      trigger: Cloud Scheduler cada hora
     │                  │
     ▼                  ▼
  BigQuery             Firestore user_balance/
  (cloudrisk.          (armies, gold actualizados)
   player_movements_   
   raw, particionada   
   por día)            
```

---

## Por qué dos componentes y no uno

| Componente | Frecuencia | Por qué separado |
|---|---|---|
| `recolector_pasos_diario` | 1×/día (batch) | Sólo necesitamos ver el repo 1 vez; el dato ya es diario |
| `puntuador_horario` | 1×/hora (batch) | Queremos scoring responsivo aunque sólo haya 1 pull/día |

El scorer trabaja sobre BQ, no sobre el pull directo: así ingesta y scoring
se desacoplan. Mañana podemos meter un Fitbit webhook que publique en el
MISMO topic, y el scorer sigue funcionando igual sin cambios.

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

# Cloud Run Service (hourly scorer)
gcloud run deploy cloudrisk-hourly-scorer \
  --source=. \
  --region=europe-west1 \
  --no-allow-unauthenticated \
  --service-account=cloudrisk-scheduler@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars=PROJECT_ID=$PROJECT_ID

# Cloud Scheduler cada hora en punto
gcloud scheduler jobs create http cloudrisk-hourly-scorer \
  --location=europe-west1 \
  --schedule='0 * * * *' \
  --uri=https://cloudrisk-hourly-scorer-xxxx.run.app/run \
  --http-method=POST \
  --oidc-service-account-email=cloudrisk-scheduler@$PROJECT_ID.iam.gserviceaccount.com
```

Terraform lo cablea solo en `infrastructure/terraform/09_scheduler.tf`.

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
- `test_scorer_applies_multipliers` (contra BQ mocked)
- `test_dedup_same_day_twice`
