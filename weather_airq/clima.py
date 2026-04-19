#ingestor automático que comprueba el tiempo en Valencia cada 30 segundos, 
# calcula una penalización o bonificación según el clima (sol o lluvia) y envía el resultado a Google
from __future__ import annotations

import json
import logging
import os
import random
import time
from datetime import datetime, timezone

import requests

#Definimos dónde estamos (Valencia) y cada cuanto tiempo trabajaremos (30 segundos)
LAT = "39.47391"
LON = "-0.37966"
CITY = "Valencia"
INTERVAL_S = int(os.environ.get("INGEST_INTERVAL_SECONDS", "30"))

#Con las variables de entorno busca las contraseñas, si no encuentra la API_KEY, activa automáticamente el modo simulacro (Mock)
API_KEY = os.environ.get("OPENWEATHER_API_KEY") or os.environ.get("CLAVE_API")
MOCK = not API_KEY

PUBSUB_PROJECT = os.environ.get("PUBSUB_PROJECT")
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC_WEATHER", "weather")  # team contract
BACKEND_INGEST_URL = os.environ.get("BACKEND_INGEST_URL")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("weather")

#Lógica del negocio. Clima. 
#Traduce el clima actual y la temperatura en un multiplicador de puntos (de 0.6 a 1.5) para el juego, 
# penalizando si hace un calor o frío extremo.
WEATHER_BASE_MULTIPLIER = {
    "Clear":        1.5,
    "Clouds":       1.2,
    "Drizzle":      1.2,
    "Rain":         0.8,
    "Thunderstorm": 0.6,
    "Snow":         0.6,
}


def _compute_multiplier(weather_main: str, temp_c: float) -> float:
    base = WEATHER_BASE_MULTIPLIER.get(weather_main, 1.0)
    if temp_c > 35 or temp_c < 5:
        base -= 0.2
    return round(max(0.6, min(1.5, base)), 3)


#Extracción de datos. Se conecta a OpenWeather, se baja el JSON con el clima de Valencia, saca solo la información necesaria y lo devuelve limpio.
def fetch_real() -> dict:
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

#hace lo mismo pero con datos generados aleatoriamente.
def fetch_mock() -> dict:
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

#Empaqueta el mensaje y decide por dónde enviarlo siguiendo este orden de prioridad:
# 1. Nube (Google Cloud): Si está configurado, lo envía a Producción.
# 2. Servidor (Backend): Si hay una dirección web, lo envía por ahí.
# 3. Pantalla (Local): Si no hay nada configurado, lo imprime aquí mismo para hacer pruebas.
def emit(message: dict) -> None:
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

#Empaqueta los datos en bruto dándoles el formato exacto que necesita el juego.
# Añade la hora exacta, el tipo de dato y calcula el multiplicador en este paso.
def _build_message(data: dict) -> dict:

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

#cada 30 segundos pide los datos, los empaqueta y los envía. Si internet falla, no se apaga, solo avisa del error y lo vuelve a intentar en la siguiente ronda.
def main() -> None:

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
