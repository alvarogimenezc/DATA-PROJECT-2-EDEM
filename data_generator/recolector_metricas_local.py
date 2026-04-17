#!/usr/bin/env python3
"""
CloudRISK — Local Metrics Collector

Local-only replacement for the Pub/Sub → BigQuery Dataflow step.
It subscribes to Pub/Sub emulator subscriptions and appends events to JSONL files
in a shared volume, which the Streamlit dashboard can read.
"""

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
        "step_events": args.steps_subscription,
        "battle_events": args.battles_subscription,
    }

    futures = []

    for prefix, sub_id in subs.items():
        sub_path = subscriber.subscription_path(args.project_id, sub_id)
        out_path = out_dir / f"{prefix}.jsonl"

        def make_cb(_out_path: Path):
            def cb(message: pubsub_v1.subscriber.message.Message) -> None:
                try:
                    data = json.loads(message.data.decode("utf-8"))
                except Exception:
                    data = {"raw": message.data.decode("utf-8", errors="replace")}
                _append_jsonl(_out_path, data, lock)
                message.ack()

            return cb

        futures.append(subscriber.subscribe(sub_path, callback=make_cb(out_path)))

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

