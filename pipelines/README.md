# pipelines/ — Jobs de streaming en Dataflow

Pipelines Apache Beam para la capa de data engineering de CloudRISK.

> **Cambio de arquitectura (2026-04):** antes había dos pipelines separados
> (`ambiental_a_bq.py` para clima/aire y `src/dataflow_pipeline/pipeline.py`
> para pasos) más un Cloud Run `puntuador_horario.py`. **Todo eso se ha
> absorbido en un único pipeline unificado** — `cloudrisk_unified.py` —
> con *stateful DoFn* por `player_id`. Los otros scripts ya no existen.

---

## `cloudrisk_unified.py` — pipeline único streaming (stateful)

Fan-in de los 3 topics Pub/Sub del juego → un único job de Dataflow → dos
sinks (Firestore para estado *hot* + BigQuery para histórico analítico).

### Topología

```
steps_ingestor/recolector_pasos_diario  ──► Pub/Sub  player-movements   ┐
weather_airq/clima.py                   ──► Pub/Sub  weather            ├─► Dataflow
weather_airq/calidad_aire.py            ──► Pub/Sub  air-quality        ┘   (stateful)
                                                                          │
                                                       ┌──────────────────┼─────────────────────┐
                                                       ▼                  ▼                     ▼
                                                  Firestore         BigQuery              BigQuery (DLQ)
                                                  user_balance/    player_scoring_events  dead_letter
                                                  users/           environmental_factors
```

### Lógica de negocio (en un solo sitio)

El `StatefulScoringDoFn` está *keyed* por `player_id` y mantiene tres piezas
de estado por usuario:

| Estado Beam | Tipo | Para qué |
|---|---|---|
| `last_position` | `ReadModifyWriteStateSpec` | Última (lat, lon, ts) para calcular distancia y velocidad |
| `armies_today` | `CombiningValueStateSpec(sum)` | Ejércitos acumulados en el día → trunca a `DAILY_ARMY_CAP` |
| `steps_today` | `CombiningValueStateSpec(sum)` | Pasos acumulados en el día → trunca a `DAILY_STEPS_CAP` (anti-trampa extra) |

Un `TimerSpec` en `ProcessingTime` (24 h) limpia `armies_today` y `steps_today`
de golpe cuando toca reset diario.

**Reglas aplicadas por evento:**

1. Haversine vs. `last_position` → `distance_m`, `speed_kmh`.
2. Speed check: si `speed_kmh > MAX_SPEED_KMH` → DLQ `anti_cheat_speed`, no acumula nada.
3. Cap de pasos diario: si `steps_today + steps_delta > DAILY_STEPS_CAP` → trunca el exceso y marca `capped=True`.
4. Multiplicador ambiental (side input `AsSingleton` desde weather + air-quality).
5. `armies_earned = (steps_permitidos // POWER_PER_STEPS) × multiplicador`.
6. Cap diario de armies: `min(armies_earned, DAILY_ARMY_CAP − armies_today)`.

### Parámetros (env vars o flags CLI)

| Parámetro | Default | Efecto |
|---|---|---|
| `POWER_PER_STEPS` | `500` | Pasos necesarios para 1 army |
| `DAILY_ARMY_CAP` | `50` | Máx armies/día por jugador |
| `DAILY_STEPS_CAP` | `30000` | Máx pasos contables/día (anti-trampa, ≈ maratón) |
| `MAX_SPEED_KMH` | `15` | Umbral anti-trampa (> 15 km/h = DLQ) |

> Nota: la bonificación **rappel ×1.5 cada 24 h** (presente en un plan
> anterior) **se retiró** en la auditoría 2026-04-17 — introducía
> dependencia temporal en el DoFn sin aportar valor de juego. La
> columna `rappel_applied BOOLEAN` queda en el schema BQ por compatibilidad
> histórica pero ya no se popula.

### Esquema BigQuery

**`cloudrisk.player_scoring_events`** — histórico por evento:

| Columna | Tipo | Notas |
|---|---|---|
| `player_id` | STRING | Identidad del jugador |
| `ts` | TIMESTAMP | Timestamp del evento (origen) |
| `lat`, `lon` | FLOAT | Posición reportada |
| `steps_delta` | INT | Pasos permitidos (tras cap) |
| `distance_m`, `speed_kmh` | FLOAT | Derivados |
| `env_multiplier` | FLOAT | 0.6–1.5 |
| `armies_earned` | INT | Ejércitos otorgados (tras caps) |
| `armies_today_after` | INT | Acumulado día tras el evento |
| `capped` | BOOLEAN | Si se truncó por cap diario de pasos |
| `rejected` | BOOLEAN | Si el evento fue rechazado |
| `rejection_reason` | STRING | e.g. `anti_cheat_speed` |
| `processed_at` | TIMESTAMP | Cuándo lo escribió el pipeline |

**`cloudrisk.environmental_factors`** — snapshots clima/aire (schema igual que antes del refactor).

**`cloudrisk.dead_letter`** — JSONs no parseables o rechazados por anti-trampa.

### Ejecutar en local con el Direct Runner

```bash
pip install -r pipelines/requirements.txt

python pipelines/cloudrisk_unified.py \
  --runner=DirectRunner \
  --project=cloudrisk-local \
  --player_sub=projects/cloudrisk-local/subscriptions/player-movements-sub \
  --weather_sub=projects/cloudrisk-local/subscriptions/weather-sub \
  --airq_sub=projects/cloudrisk-local/subscriptions/air-quality-sub \
  --scoring_table=cloudrisk-local:cloudrisk.player_scoring_events \
  --env_table=cloudrisk-local:cloudrisk.environmental_factors \
  --dlq_table=cloudrisk-local:cloudrisk.dead_letter \
  --streaming
```

### Desplegar a Dataflow (producción)

Terraform construye y despliega el job vía Flex Template
(`infrastructure/terraform/12_dataflow.tf`). Manual:

```bash
python pipelines/cloudrisk_unified.py \
  --runner=DataflowRunner \
  --project=cloudrisk-492619 \
  --region=europe-west1 \
  --temp_location=gs://cloudrisk-492619-dataflow/tmp \
  --staging_location=gs://cloudrisk-492619-dataflow/staging \
  --player_sub=projects/cloudrisk-492619/subscriptions/player-movements-sub \
  --weather_sub=projects/cloudrisk-492619/subscriptions/weather-sub \
  --airq_sub=projects/cloudrisk-492619/subscriptions/air-quality-sub \
  --scoring_table=cloudrisk-492619:cloudrisk.player_scoring_events \
  --env_table=cloudrisk-492619:cloudrisk.environmental_factors \
  --dlq_table=cloudrisk-492619:cloudrisk.dead_letter \
  --streaming
```

El job de streaming corre indefinidamente hasta `gcloud dataflow jobs cancel JOB_ID`.

### Queries de ejemplo

```sql
-- Último multiplicador ambiental por tipo (últimos 5 min)
SELECT type, ARRAY_AGG(multiplier ORDER BY ts DESC LIMIT 1)[OFFSET(0)] AS latest
FROM `cloudrisk-492619.cloudrisk.environmental_factors`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
GROUP BY type;

-- Top jugadores por pasos del último mes
SELECT player_id, SUM(steps_delta) AS total_steps
FROM `cloudrisk-492619.cloudrisk.player_scoring_events`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND rejected = FALSE
GROUP BY player_id
ORDER BY total_steps DESC
LIMIT 10;

-- Eventos rechazados (DLQ)
SELECT player_id, rejection_reason, COUNT(*) AS n
FROM `cloudrisk-492619.cloudrisk.dead_letter`
WHERE processed_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY player_id, rejection_reason
ORDER BY n DESC;
```

El dataset `cloudrisk` debe existir antes de la primera ejecución — ver
`infrastructure/terraform/04_bigquery.tf`.

### Tests

Los tests unitarios usan `apache_beam.testing.TestPipeline` + `TestStream`
para simular ventanas de tiempo y timers sin depender de GCP real:

```bash
pytest tests/pipelines/test_cloudrisk_unified.py -v
```

Cubren: evento normal → BQ + Firestore, evento con velocidad > 15 km/h → DLQ,
cap diario de pasos, cap diario de armies, reset 24 h del timer.
