#!/usr/bin/env python3
"""Create Pub/Sub topics + subscriptions on the local emulator.

Usage (with emulator running on :8085):
    $env:PUBSUB_EMULATOR_HOST = "localhost:8085"
    python scripts/setup_local_pubsub.py
"""
import os

os.environ.setdefault("PUBSUB_EMULATOR_HOST", "localhost:8085")

from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists

PROJECT = "cloudrisk-local"

TOPICS_AND_SUBS = {
    "player-movements": "player-movements-sub",
    "weather-events": "weather-sub",
    "airquality-events": "air-quality-sub",
}


def main():
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    for topic_name, sub_name in TOPICS_AND_SUBS.items():
        topic_path = publisher.topic_path(PROJECT, topic_name)
        sub_path = subscriber.subscription_path(PROJECT, sub_name)

        try:
            publisher.create_topic(request={"name": topic_path})
            print(f"  Topic creado: {topic_path}")
        except AlreadyExists:
            print(f"  Topic ya existe: {topic_path}")

        try:
            subscriber.create_subscription(request={"name": sub_path, "topic": topic_path})
            print(f"  Subscripcion creada: {sub_path}")
        except AlreadyExists:
            print(f"  Subscripcion ya existe: {sub_path}")

    print("\nPub/Sub emulator listo para E2E local.")


if __name__ == "__main__":
    main()
