#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from google.cloud import pubsub_v1


def _append_jsonl(path: Path, row: dict, lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False)
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _jsonl_callback_for(out_path: Path, lock: threading.Lock):
    """Construye el callback de Pub/Sub que parsea el mensaje y lo escribe a
    `out_path`. La factoría es necesaria porque cada subscription tiene su
    propio fichero de salida — usamos default-args en vez de un closure
    para que el path quede fijado en el momento de la creación, no por
    captura léxica (más fácil de seguir en stack traces)."""

    def callback(message: "pubsub_v1.subscriber.message.Message", _path=out_path) -> None:
        try:
            data = json.loads(message.data.decode("utf-8"))
        except Exception:
            data = {"raw": message.data.decode("utf-8", errors="replace")}
        _append_jsonl(_path, data, lock)
        message.ack()

    return callback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", required=True)
    parser.add_argument("--out_dir", default=os.environ.get("CLOUDRISK_LOCAL_METRICS_DIR", "/metrics"))
    parser.add_argument("--location_subscription", required=True)
    parser.add_argument("--steps_subscription", required=True)
    parser.add_argument("--battles_subscription", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    lock = threading.Lock()

    subscriber = pubsub_v1.SubscriberClient()

    subs = {
        "location_events": args.location_subscription,
        "step_events":     args.steps_subscription,
        "battle_events":   args.battles_subscription,
    }

    futures = []
    for prefix, sub_id in subs.items():
        sub_path = subscriber.subscription_path(args.project_id, sub_id)
        out_path = out_dir / f"{prefix}.jsonl"
        callback = _jsonl_callback_for(out_path, lock)
        futures.append(subscriber.subscribe(sub_path, callback=callback))

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        for f in futures:
            f.cancel()


if __name__ == "__main__":
    main()

