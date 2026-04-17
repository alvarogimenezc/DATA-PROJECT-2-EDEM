# pipelines/ — jobs de streaming en Dataflow

Pipelines Apache Beam para la capa de data engineering de CloudRISK.

## `ambiental_a_bq.py` — clima/aire → BigQuery

Hace streaming de los mensajes emitidos por `weather_airq/{air_quality,weather}.py`
hacia una única tabla de BigQuery para que el dashboard pueda consultar el histórico
de la señal del multiplicador.

### Topología

```
weather_airq/calidad_aire.py  ──► Pub/Sub cloudrisk-air-events       ┐
weather_airq/clima.py      ──► Pub/Sub cloudrisk-weather-events   ┴► Beam → BQ
                                                                     │
                                                                     ▼
                                       cloudrisk.environmental_factors
```

### Esquema BigQuery

| Columna | Tipo | Notas |
|---|---|---|
| `ts` | TIMESTAMP | Cuándo midió el ingestor el valor (desde el mensaje). |
| `type` | STRING | `air_quality` o `weather`. |
| `multiplier` | FLOAT | El factor 0.6–1.5. |
| `raw_payload` | STRING | JSON original completo. Útil para forensics. |
| `processed_at` | TIMESTAMP | Cuándo escribió la fila el pipeline. |

Los mensajes malos (JSON no parseable, `type` desconocido, multiplier ausente)
se enrutan a una dead-letter side output con logging en vez de tumbar el
bundle.

### Ejecutar en local con el Direct Runner

Útil para verificación rápida — necesita que las subscripciones Pub/Sub
ya existan (el script NO las crea).

```bash
pip install -r pipelines/requirements.txt

python pipelines/ambiental_a_bq.py \
  --runner=DirectRunner \
  --project=cloudrisk-492619 \
  --air_subscription=projects/cloudrisk-492619/subscriptions/cloudrisk-air-events-sub \
  --weather_subscription=projects/cloudrisk-492619/subscriptions/cloudrisk-weather-events-sub \
  --output_table=cloudrisk-492619:cloudrisk.environmental_factors
```

### Desplegar a Dataflow (producción)

```bash
python pipelines/ambiental_a_bq.py \
  --runner=DataflowRunner \
  --project=cloudrisk-492619 \
  --region=europe-west1 \
  --temp_location=gs://cloudrisk-492619-dataflow/tmp \
  --staging_location=gs://cloudrisk-492619-dataflow/staging \
  --air_subscription=projects/cloudrisk-492619/subscriptions/cloudrisk-air-events-sub \
  --weather_subscription=projects/cloudrisk-492619/subscriptions/cloudrisk-weather-events-sub \
  --output_table=cloudrisk-492619:cloudrisk.environmental_factors \
  --streaming
```

Dataflow auto-escalará los workers; el job de streaming corre indefinidamente
hasta que hagas `gcloud dataflow jobs cancel JOB_ID`.

### Queries de ejemplo sobre la tabla BQ resultante

```sql
-- Último multiplier por tipo
SELECT type, ARRAY_AGG(multiplier ORDER BY ts DESC LIMIT 1)[OFFSET(0)] AS latest
FROM `cloudrisk-492619.cloudrisk.environmental_factors`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
GROUP BY type;

-- Media por hora
SELECT TIMESTAMP_TRUNC(ts, HOUR) AS hour, type, AVG(multiplier) AS avg_mult
FROM `cloudrisk-492619.cloudrisk.environmental_factors`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY hour, type
ORDER BY hour DESC;

-- Aire × clima combinado a lo largo del tiempo (asume que ambos ingestors emiten con cadencia similar)
WITH paired AS (
  SELECT TIMESTAMP_TRUNC(ts, MINUTE) AS minute, type, AVG(multiplier) AS m
  FROM `cloudrisk-492619.cloudrisk.environmental_factors`
  GROUP BY minute, type
)
SELECT minute,
       MAX(IF(type='air_quality', m, NULL)) AS air,
       MAX(IF(type='weather', m, NULL))     AS weather,
       MAX(IF(type='air_quality', m, NULL)) * MAX(IF(type='weather', m, NULL)) AS combined
FROM paired
GROUP BY minute
ORDER BY minute DESC
LIMIT 60;
```

El dataset `cloudrisk` debe existir antes de la primera ejecución — mira
`docs/GCP_TUTORIAL.md` para el comando `bq mk`.
