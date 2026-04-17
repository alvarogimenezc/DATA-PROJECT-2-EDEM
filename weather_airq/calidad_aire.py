"""
CloudRISK — Air Quality Ingestor
Polls OpenWeatherMap's air pollution API for Valencia every 30 seconds
and publishes a normalised multiplier to Pub/Sub topic `air-quality`.

Two execution modes:
    - real:  uses OPENWEATHER_API_KEY (via Secret Manager in Cloud Run)
    - mock:  generates synthetic AQI values when the key is absent

Contract multiplier range: 0.6 (worst air) to 1.5 (best air).
Formula: multiplier = 1.5 - (AQI - 1) * 0.225    for AQI ∈ {1,2,3,4,5}

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
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC_AIR", "air-quality")  # team contract
BACKEND_INGEST_URL = os.environ.get("BACKEND_INGEST_URL")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("air_quality")


def _multiplier_from_aqi(aqi: int) -> float:
    """Team formula. AQI 1 → 1.5 (best), AQI 5 → 0.6 (worst)."""
    return round(max(0.6, min(1.5, 1.5 - (aqi - 1) * 0.225)), 3)


def fetch_real() -> dict:
    url = (
        "https://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    item = r.json()["list"][0]
    return {
        "ts_unix": item["dt"],
        "aqi": item["main"]["aqi"],
        "components": item["components"],
    }


def fetch_mock() -> dict:
    """Generate a believable AQI sample (mostly 1-3, occasional 4-5)."""
    weights = [0.4, 0.3, 0.2, 0.07, 0.03]   # AQI 1..5
    aqi = random.choices([1, 2, 3, 4, 5], weights=weights)[0]
    return {
        "ts_unix": int(time.time()),
        "aqi": aqi,
        "components": {
            "co": round(random.uniform(200, 800), 2),
            "no2": round(random.uniform(5, 60), 2),
            "o3": round(random.uniform(40, 130), 2),
            "pm2_5": round(random.uniform(3, 35), 2),
            "pm10": round(random.uniform(5, 60), 2),
        },
    }


def emit(message: dict) -> None:
    payload = json.dumps(message)
    if PUBSUB_PROJECT:
        from google.cloud import pubsub_v1   # lazy import
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PUBSUB_PROJECT, PUBSUB_TOPIC)
        future = publisher.publish(topic_path, payload.encode("utf-8"))
        future.result(timeout=10)
        log.info("pubsub %s: %s", PUBSUB_TOPIC, payload)
    elif BACKEND_INGEST_URL:
        r = requests.post(BACKEND_INGEST_URL, json=message, timeout=5)
        log.info("POST %s → %d", BACKEND_INGEST_URL, r.status_code)
    else:
        print(payload, flush=True)


def main() -> None:
    log.info("Starting air_quality ingestor (mode=%s, interval=%ds)",
             "MOCK" if MOCK else "REAL", INTERVAL_S)
    while True:
        try:
            data = fetch_mock() if MOCK else fetch_real()
            multiplier = _multiplier_from_aqi(data["aqi"])
            message = {
                "type": "air_quality",
                "ts": datetime.fromtimestamp(data["ts_unix"], tz=timezone.utc).isoformat(),
                "city": CITY,
                "aqi": data["aqi"],
                "indice_multiplicador_aire": multiplier,
                "components": data["components"],
                "source": "mock" if MOCK else "openweathermap",
            }
            emit(message)
        except Exception as exc:   # noqa: BLE001
            log.warning("ingest cycle failed: %s", exc)
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
