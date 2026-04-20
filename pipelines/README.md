# 🧠 pipelines/ — El Cerebro de CloudRISK (Dataflow)

Este directorio contiene el archivo `cloudrisk_unified.py`, que es el motor principal del juego. Es un programa construido con Apache Beam que está **siempre encendido** escuchando los datos que llegan de internet.

Su misión es sencilla: recibir los pasos de los jugadores, vigilar que nadie haga trampas, calcular los puntos usando el clima real, y mandar los ejércitos al móvil del jugador.

---

## Las Reglas del Juego (Qué hace el código)

Cada vez que un jugador da un paso, el sistema hace estas comprobaciones en milisegundos:

1. **Radar de Velocidad (Anti-trampas):** Compara dónde estabas hace un rato y dónde estás ahora. Si vas a más de **15 km/h**, el sistema asume que vas en bici o coche. El evento se marca como trampa y se tira a la basura.
2. **Tope de Pasos Diarios:** Vigila que nadie reporte más de **30.000 pasos** al día (para evitar cuentas robot o abusos). Lo que pase de ahí, no cuenta.
3. **El Clima Importa:** Revisa qué tiempo hace en Valencia en ese segundo exacto. Si hace sol y el aire es puro, tus pasos valen más. Si hay tormenta, valen menos.
4. **Calculadora de Tropas:** Transforma los pasos limpios en tropas (la regla base es **500 pasos = 1 ejército**).
5. **Tope de Tropas:** Se asegura de que nadie gane más de **50 ejércitos** en un solo día.

*(Todos estos límites se pueden cambiar en cualquier momento sin tocar el código, usando variables de entorno en GCP).*

---

## El Viaje de los Datos

¿De dónde viene la información y a dónde va dentro de este pipeline?

```text
1. ENTRADAS                     2. CEREBRO                  3. SALIDAS
(Pub/Sub)                       (Dataflow)                  (Bases de datos)

[Pasos de los jugadores] ─┐                               ┌─► FIRESTORE (El juego en vivo)
[El clima actual]        ─┼──►  PIPELINE DE CLOUDRISK ────┤   Actualiza la pantalla del móvil.
[La calidad del aire]    ─┘     Calcula y da puntos       │
                                                          └─► BIGQUERY (El historial)
                                                              Guarda los rankings y trampas.

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
Como guardamos una copia de todo en BigQuery, se pueden lanzar consultas SQL para ver cómo va la partida.

```sql
-- Ejemplo 1: Ver quiénes son los que más han caminado este mes:
SELECT player_id, SUM(steps_delta) AS total_pasos
FROM `cloudrisk-492619.cloudrisk.player_scoring_events`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND capped = FALSE
GROUP BY player_id
ORDER BY total_pasos DESC
LIMIT 10;

-- Ejemplo 2: Top jugadores por pasos del último mes
SELECT player_id, SUM(steps_delta) AS total_steps
FROM `cloudrisk-492619.cloudrisk.player_scoring_events`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND rejected = FALSE
GROUP BY player_id
ORDER BY total_steps DESC
LIMIT 10;

-- Ejemplo 3: Cazar a los tramposos (Gente que va a más de 15km/h):
SELECT player_id, rejection_reason, COUNT(*) AS intentos_trampa
FROM `cloudrisk-492619.cloudrisk.dead_letter`
WHERE processed_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY player_id, rejection_reason
ORDER BY intentos_trampa DESC;
```


### Tests

Los tests unitarios usan `apache_beam.testing.TestPipeline` + `TestStream`
para simular ventanas de tiempo y timers sin depender de GCP real:

```bash
pytest tests/pipelines/test_cloudrisk_unified.py -v
```


