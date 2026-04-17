"""Repository: Pub/Sub publish operations."""

from __future__ import annotations


import os
import json
from datetime import datetime

from cloudrisk_api.configuracion import settings

USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"

if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store
else:
    from google.cloud import pubsub_v1
    publisher = pubsub_v1.PublisherClient()


def publish_message(topic_id: str, message: dict) -> str:
    if USE_LOCAL:
        store.pubsub_publish(topic_id, message)
        return "local-msg-id"
    else:
        topic_path = publisher.topic_path(settings.PROJECT_ID, topic_id)
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        return future.result()


def publish_location_event(user_id: str, lat: float, lng: float, zone: dict | None) -> None:
    publish_message(settings.PUBSUB_TOPIC_LOCATION, {
        "user_id": user_id, "lat": lat, "lng": lng,
        "zone_id": zone["id"] if zone else None,
        "zone_name": zone["name"] if zone else None,
        "timestamp": datetime.utcnow().isoformat(),
    })


def publish_step_event(
    user_id: str,
    steps: int,
    power_earned: int,
    *,
    source: str = "backend_sync",
    latitude: float | None = None,
    longitude: float | None = None,
    speed_mps: float | None = None,
) -> None:
    """Publish a step event to the ``player-movements`` topic.

    The shape of the message matches what Noelia+Martha's Dataflow
    pipeline (and the steps_ingestor/hourly_scorer) expect:

    ================== =============================================
    Field              Source
    ================== =============================================
    player_id          session user (game) / mapping file (tracker)
    steps_delta        pasos ganados en esta publicación (no el total)
    power_earned       puntos derivados (compat con backend legacy)
    source             "backend_sync" | "real" | "synthetic_walker"
    latitude/longitude opcional, solo presente cuando hay GPS
    speed_mps          opcional, idem
    timestamp          ISO-8601 UTC
    ================== =============================================

    All consumers (Dataflow, hourly_scorer, dashboards) filter by
    ``source`` so the same topic can carry real + synthetic + sync
    events without confusion.
    """
    message: dict = {
        "player_id": user_id,
        "steps_delta": steps,
        "power_earned": power_earned,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if latitude is not None:
        message["latitude"] = latitude
    if longitude is not None:
        message["longitude"] = longitude
    if speed_mps is not None:
        message["speed_mps"] = speed_mps
    publish_message(settings.PUBSUB_TOPIC_STEPS, message)


def publish_battle_event(battle: dict, event_type: str) -> None:
    publish_message(settings.PUBSUB_TOPIC_BATTLES, {
        "event_type": event_type, "battle_id": battle["id"],
        "zone_id": battle["zone_id"],
        "attacker_clan_id": battle["attacker_clan_id"],
        "defender_clan_id": battle.get("defender_clan_id"),
        "attacker_power": battle["attacker_power"],
        "defender_power": battle["defender_power"],
        "timestamp": datetime.utcnow().isoformat(),
    })
