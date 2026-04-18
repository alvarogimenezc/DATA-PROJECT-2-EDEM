"""
CloudRISK — Weather Ingestor
Polls OpenWeatherMap for Valencia's weather every 30 seconds and publishes
a normalised multiplier to Pub/Sub topic `weather`.

Two execution modes:
    - real:  uses OPENWEATHER_API_KEY (via Secret Manager in Cloud Run)
    - mock:  generates synthetic weather values when the key is absent

Contract multiplier range: 0.6 (extreme weather) to 1.5 (clear + mild).
Extra penalty of -0.2 when temperature is outside [5°C, 35°C].

EDEM. Master Big Data & Cloud 2025/2026
Professor: Javi Briones & Adriana Campos
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from datetime import datetime, timezone

import requests

LAT = "39.47391"
LON = "-0.37966"
CITY = "Valencia"
INTERVAL_S = int(os.environ.get("INGEST_INTERVAL_SECONDS", "30"))

API_KEY = os.environ.get("OPENWEATHER_API_KEY") or os.environ.get("CLAVE_API")
MOCK = not API_KEY

PUBSUB_PROJECT = os.environ.get("PUBSUB_PROJECT")
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC_WEATHER", "weather")  # team contract
BACKEND_INGEST_URL = os.environ.get("BACKEND_INGEST_URL")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("weather")

WEATHER_BASE_MULTIPLIER = {
    "Clear":        1.5,
    "Clouds":       1.2,
    "Drizzle":      1.2,
    "Rain":         0.8,
    "Thunderstorm": 0.6,
    "Snow":         0.6,
}


def _compute_multiplier(weather_main: str, temp_c: float) -> float:
    """Mapea (clima, temperatura) a un multiplicador acotado a [0.6, 1.5].

    El base sale de la tabla `WEATHER_BASE_MULTIPLIER`. Aplicamos -0.2
    si la temperatura está fuera del rango cómodo [5°C, 35°C] (frío extremo
    o calor extremo desincentivan caminar)."""
    base = WEATHER_BASE_MULTIPLIER.get(weather_main, 1.0)
    if temp_c > 35 or temp_c < 5:
        base -= 0.2
    return round(max(0.6, min(1.5, base)), 3)


def fetch_real() -> dict:
    """Llama a la API real de OpenWeatherMap y aplana la respuesta a un dict
    con sólo los campos que necesitamos. `r.raise_for_status()` deja que el
    bucle principal lo capture y haga reintento en el siguiente tick."""
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "ts_unix":     data.get("dt", int(time.time())),
        "temp":        data["main"]["temp"],
        "humidity":    data["main"].get("humidity"),
        "rain_mm_1h":  data.get("rain", {}).get("1h", 0),
        "clouds_pct":  data["clouds"]["all"],
        "main":        data["weather"][0]["main"],
        "description": data["weather"][0]["description"],
    }


def fetch_mock() -> dict:
    """Genera una muestra sintética plausible de tiempo en Valencia.

    Modo cuando no hay `OPENWEATHER_API_KEY` — útil para dev y tests sin
    credenciales. Las probabilidades de cada estado están sesgadas hacia
    "Clear/Clouds" porque es lo más típico aquí."""
    main = random.choices(
        list(WEATHER_BASE_MULTIPLIER.keys()),
        weights=[0.55, 0.20, 0.05, 0.10, 0.05, 0.05],
    )[0]
    temp = round(random.uniform(8, 32), 1)
    return {
        "ts_unix":     int(time.time()),
        "temp":        temp,
        "humidity":    random.randint(35, 90),
        "rain_mm_1h":  round(random.uniform(0, 4), 2) if main == "Rain" else 0,
        "clouds_pct":  random.randint(0, 100),
        "main":        main,
        "description": main.lower(),
    }


def emit(message: dict) -> None:
    """Publica el mensaje según el sink disponible. Hay 3 modos según envs:

      1. `PUBSUB_PROJECT` → publica al topic `weather` (modo prod / Dataflow).
      2. `BACKEND_INGEST_URL` → POST HTTP al backend (modo single-host).
      3. ninguno → vuelca a stdout (modo dev sin emuladores).

    El primer match gana (early return). Cada caso loguea para que el
    operador vea por dónde fue el mensaje."""
    payload = json.dumps(message)
    if PUBSUB_PROJECT:
        from google.cloud import pubsub_v1
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PUBSUB_PROJECT, PUBSUB_TOPIC)
        future = publisher.publish(topic_path, payload.encode("utf-8"))
        future.result(timeout=10)
        log.info("pubsub %s: %s", PUBSUB_TOPIC, payload)
        return
    if BACKEND_INGEST_URL:
        r = requests.post(BACKEND_INGEST_URL, json=message, timeout=5)
        log.info("POST %s → %d", BACKEND_INGEST_URL, r.status_code)
        return
    print(payload, flush=True)


def _build_message(data: dict) -> dict:
    """Convierte la respuesta cruda (real o mock) en el JSON que viaja por el
    sink. El nombre del campo `indice_multiplicador_tiempo` es contrato del
    pipeline Dataflow — no renombrar sin coordinar."""
    return {
        "type": "weather",
        "ts": datetime.fromtimestamp(data["ts_unix"], tz=timezone.utc).isoformat(),
        "city": CITY,
        "temp_c": data["temp"],
        "weather_main": data["main"],
        "weather_description": data["description"],
        "rain_mm_1h": data["rain_mm_1h"],
        "clouds_pct": data["clouds_pct"],
        "humidity_pct": data["humidity"],
        "indice_multiplicador_tiempo": _compute_multiplier(data["main"], data["temp"]),
        "source": "mock" if MOCK else "openweathermap",
    }


def main() -> None:
    """Bucle infinito: cada `INTERVAL_S` segundos pide datos (mock/real),
    construye el mensaje y lo emite. Los errores no tumban el ingestor —
    se loguean y se reintenta en el siguiente tick."""
    log.info("Starting weather ingestor (mode=%s, interval=%ds)",
             "MOCK" if MOCK else "REAL", INTERVAL_S)
    while True:
        try:
            data = fetch_mock() if MOCK else fetch_real()
            emit(_build_message(data))
        except Exception as exc:
            log.warning("ingest cycle failed: %s", exc)
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
