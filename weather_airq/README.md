# weather_airq — ingestor de multiplicadores ambientales

Dos scripts de larga duración que calculan un multiplicador `0.6 – 1.5` y lo envían
en streaming al sistema. El backend lo aplica después cuando los jugadores despliegan
tropas (`armies_deployed = base * air_multiplier * weather_multiplier`).

Adaptado del [`alvarogimenezc/DATA-PROJECT-2-EDEM/weather_airq`](https://github.com/alvarogimenezc/DATA-PROJECT-2-EDEM/tree/main/weather_airq) del equipo.

## Qué hace cada script

| Archivo | Fuente de datos | Fórmula del multiplier | Campo `type` de salida |
|---|---|---|---|
| `calidad_aire.py` | OpenWeatherMap Air Pollution API (AQI 1-5) | `1.5 - (AQI - 1) * 0.225` | `"air_quality"` |
| `clima.py` | OpenWeatherMap Current Weather API | base según estado del cielo, `-0.2` si la temperatura es extrema | `"weather"` |

Ambos acotan el valor final a `[0.6, 1.5]`, ambos publican cada
`INGEST_INTERVAL_SECONDS` (por defecto 30 s).

## Modos

| Variable env | Efecto |
|---|---|
| `OPENWEATHER_API_KEY` definida | **Modo real** — pega contra OpenWeatherMap |
| `OPENWEATHER_API_KEY` sin definir | **Modo mock** — genera muestras sintéticas de AQI y clima (para que la demo corra end-to-end sin dependencia externa) |

## Sinks

Los mismos scripts pueden entregar el multiplier a uno de tres sitios:

| Variables env | A dónde va el mensaje |
|---|---|
| `PUBSUB_PROJECT` + `PUBSUB_TOPIC_AIR` / `PUBSUB_TOPIC_WEATHER` | Google Pub/Sub (real o emulador) |
| `BACKEND_INGEST_URL` | HTTP `POST` al backend (p. ej. `http://localhost:8080/api/v1/multipliers/ingest`) |
| ninguna | `stdout` (una línea JSON por ciclo) |

## Ejecutar en local

```bash
cd weather_airq
pip install -r requirements.txt

# Modo mock, volcado a stdout (cero configuración)
python calidad_aire.py
python clima.py

# Modo real, empujando al backend en ejecución
export OPENWEATHER_API_KEY=...                     # añádela a .env.local (gitignored)
export BACKEND_INGEST_URL=http://localhost:8080/api/v1/multipliers/ingest
python calidad_aire.py &
python clima.py &
```

## Ejecutar en Docker (dos imágenes desde un mismo Dockerfile)

```bash
docker build -t cloudrisk/air-ingestor     --target air     weather_airq/
docker build -t cloudrisk/weather-ingestor --target weather weather_airq/

# Cada uno corre en su propio contenedor; ambos comparten las convenciones de env vars de arriba.
docker run -e BACKEND_INGEST_URL=http://host.docker.internal:8080/api/v1/multipliers/ingest cloudrisk/air-ingestor
docker run -e BACKEND_INGEST_URL=http://host.docker.internal:8080/api/v1/multipliers/ingest cloudrisk/weather-ingestor
```

## Mensaje de ejemplo (aire)

```json
{
  "type": "air_quality",
  "ts": "2026-04-14T20:42:00+00:00",
  "ciudad": "Valencia",
  "aqi": 2,
  "indice_multiplicador_aire": 1.275,
  "components": {"co": 423.5, "no2": 18.4, "o3": 71.2, "pm2_5": 12.8, "pm10": 18.6},
  "source": "openweathermap"
}
```

## Mensaje de ejemplo (clima)

```json
{
  "type": "weather",
  "ts": "2026-04-14T20:42:00+00:00",
  "ciudad": "Valencia",
  "temp_c": 23.4,
  "weather_main": "Clouds",
  "weather_description": "scattered clouds",
  "rain_mm_1h": 0,
  "clouds_pct": 40,
  "humidity_pct": 62,
  "indice_multiplicador_tiempo": 1.2,
  "source": "openweathermap"
}
```

## Dónde acaban estos mensajes en el resto del stack

```
weather_airq → Pub/Sub → pipeline Dataflow → BigQuery (histórico)
                       ↘
                         CloudRISK API /api/v1/multipliers/ingest → caché en memoria
                                                                 ↓
                                            armies_deployed = base * mult
```
