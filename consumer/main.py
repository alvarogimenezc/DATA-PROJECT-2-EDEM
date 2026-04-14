import os
import json
from google.cloud import pubsub_v1
from concurrent.futures import TimeoutError

PROJECT_ID = os.environ.get("PROJECT_ID", "cloudrisk-492619")
SUBSCRIPTION_ID = os.environ.get("SUBSCRIPTION_ID", "player-movements-consumer")

subscriber = pubsub_v1.SubscriberClient()
sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)


def callback(message):
    try:
        event = json.loads(message.data.decode("utf-8"))
        print(
            f"[consumer] msg_id={message.message_id} "
            f"player={event.get('player_id')} "
            f"pos=({event.get('latitude'):.5f},{event.get('longitude'):.5f}) "
            f"speed={event.get('speed_mps')} "
            f"ts={event.get('timestamp')}",
            flush=True,
        )
        message.ack()
    except Exception as e:
        print(f"[consumer] ERROR msg_id={message.message_id}: {e}", flush=True)
        message.nack()


print(f"[consumer] Escuchando en {sub_path}", flush=True)
streaming_pull = subscriber.subscribe(sub_path, callback=callback)
try:
    streaming_pull.result()
except (KeyboardInterrupt, TimeoutError):
    streaming_pull.cancel()
    streaming_pull.result()
