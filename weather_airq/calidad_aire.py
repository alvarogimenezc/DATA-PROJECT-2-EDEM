#Ingestor de Calidad del Aire. Su función es actuar como un sensor que alimenta nuestro juego cada 30 segundos.
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
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC_AIR", "air-quality") 
BACKEND_INGEST_URL = os.environ.get("BACKEND_INGEST_URL")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("air_quality")

#Lógica del negocio. Calidad del aire. Recibe la contaminación real (de 1 al 5) y la convierte en el multiplicador de tropas.
def _multiplier_from_aqi(aqi: int) -> float:
#Nos aseguramos de que el resultado nunca sea menor de 0.6 (penalización máxima) ni mayor de 1.5 (bonus máximo).
    return round(max(0.6, min(1.5, 1.5 - (aqi - 1) * 0.225)), 3)

#se conecta a OpenWeather, se baja el JSON con la contaminación de Valencia, saca solo la información necesaria y lo devuelve limpio.
def fetch_real() -> dict: 
    url = (
        "https://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    item = r.json()["list"][0]
    return {
        "ts_unix":    item["dt"],
        "aqi":        item["main"]["aqi"],
        "components": item["components"],
    }

#hace lo mismo pero con datos generados aleatoriamente.
def fetch_mock() -> dict:

    weights = [0.4, 0.3, 0.2, 0.07, 0.03]   # AQI 1..5
    aqi = random.choices([1, 2, 3, 4, 5], weights=weights)[0]
    return {
        "ts_unix": int(time.time()),
        "aqi": aqi,
        "components": {
            "co":    round(random.uniform(200, 800), 2),
            "no2":   round(random.uniform(5, 60), 2),
            "o3":    round(random.uniform(40, 130), 2),
            "pm2_5": round(random.uniform(3, 35), 2),
            "pm10":  round(random.uniform(5, 60), 2),
        },
    }

#Arranca el motor de Pub/Sub, busca el Topic air-quality y dispara el mensaje hacia la nube. 
#Si no hay Google Cloud configurado, simplemente lo imprime en tu pantalla para poder probarlo localmente.
def emit(message: dict) -> None:
    payload = json.dumps(message)
    if PUBSUB_PROJECT:
        from google.cloud import pubsub_v1   # lazy import
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

#Coge los datos brutos recién extraídos y los estructura en el esquema JSON que viaja hacia el pipeline
def _build_message(data: dict) -> dict:
    """Convierte la respuesta cruda en el JSON a publicar. El nombre del
    campo `indice_multiplicador_aire` es contrato con el pipeline Dataflow
    — no renombrar."""
    return {
        "type": "air_quality",
        "ts": datetime.fromtimestamp(data["ts_unix"], tz=timezone.utc).isoformat(),
        "city": CITY,
        "aqi": data["aqi"],
        "indice_multiplicador_aire": _multiplier_from_aqi(data["aqi"]),
        "components": data["components"],
        "source": "mock" if MOCK else "openweathermap",
    }

#bucle infinito a prueba de fallos. Cada 30 segundos repite este ciclo exacto: Lee los datos del aire, 
#calcula el multiplicador y envía el mensaje a la nube.
# si internet falla, avisa del error y espera 30 segundos para volver a intentarlo.
# Borras el while True y el sleep. El main se queda así de simple:
def main() -> None:
    log.info("Ejecutando ingestor una sola vez...")
    try:
        data = fetch_mock() if MOCK else fetch_real()
        emit(_build_message(data))
    except Exception as exc:
        log.warning("ingest cycle failed: %s", exc)

if __name__ == "__main__":
    main()