"""
CloudRISK — Pub/Sub Debug Consumer
Subscribes to `player-movements-sub` using the PULL model and prints
each message to stdout. Intentionally simple: real processing lives
in the Dataflow pipeline (Noelia + Martha). This service exists so the
team can tail Pub/Sub activity from docker compose without gcloud CLI.

Why PULL (and not PUSH)?
    The consumer controls the pacing — no HTTP endpoint to expose, no
    deadletter surprises if the container restarts. For a debug tool
    that may run on the dev laptop, PULL is the simpler choice.

EDEM. Master Big Data & Cloud 2025/2026
Professor: Javi Briones & Adriana Campos
"""

from datetime import datetime, timezone
import json
import logging
import os
import signal
import sys

from google.cloud import pubsub_v1

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("consumer")

PROJECT_ID = os.environ.get("PUBSUB_PROJECT", "cloudrisk-492619")
SUBSCRIPTION = os.environ.get("SUBSCRIPTION", "player-movements-sub")


""" Helpful functions """
def iso_now():
    """
    Get the current timestamp in ISO format.
    Returns:
        str: Current timestamp in ISO format.
    """

    return datetime.now(timezone.utc).isoformat()


def _callback(message):
    """
    Handle a single Pub/Sub message: parse, log, and ack.
    Args:
        message (pubsub_v1.subscriber.message.Message): The received message.
    Returns:
        None
    """

    try:
        data = json.loads(message.data.decode("utf-8"))
        log.info(
            f"[{data.get('timestamp','?')}] "
            f"{data.get('player_id','?'):<20} "
            f"lat={data.get('latitude',0):.4f} "
            f"lon={data.get('longitude',0):.4f} "
            f"speed={data.get('speed_mps','?')} m/s"
        )
    except Exception as exc:
        log.warning(f"Failed to parse message {message.message_id}: {exc}")
    finally:
        message.ack()


""" Main loop """
def main():
    """
    Start the streaming pull subscriber and block until SIGTERM or Ctrl+C.
    Returns:
        None
    """

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION)

    log.info(f"Listening on {sub_path}... (Ctrl+C to stop)")
    future = subscriber.subscribe(sub_path, callback=_callback)

    # Graceful shutdown on SIGTERM (Cloud Run sends this).
    signal.signal(signal.SIGTERM, lambda *a: future.cancel())

    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()
    except Exception as exc:
        log.error(f"Stream error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
