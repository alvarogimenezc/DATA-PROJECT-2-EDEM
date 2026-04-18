#!/usr/bin/env python3
"""
recolector_pasos_diario.py — Cloud Run Job que tira pasos diarios desde el repo
`FranciscoAlvarezVaras/random_tracker` y los publica a Pub/Sub.

Corre 1 vez al día (Cloud Scheduler → Cloud Run Job). Puede correrse a mano
sobre un día pasado para backfill. Es idempotente: dedupe en Firestore por
fecha → re-ejecutar el mismo día no duplica.

Flujo
-----
  1. GET https://raw.githubusercontent.com/FranciscoAlvarezVaras/random_tracker/main/<file>
  2. Parsear el JSON (schema de random_tracker — ver README.md).
  3. Por cada movement, construir evento CloudRISK:
         {player_id, timestamp, latitude, longitude, speed_mps, steps_delta, source="real"}
  4. Publicar a topic `player-movements`.
  5. Escribir marker idempotencia: `step_ingests/{YYYY-MM-DD}` en Firestore.

Variables de entorno
--------------------
  PROJECT_ID       (requerido) — GCP project.
  TRACKER_REPO     (default: FranciscoAlvarezVaras/random_tracker) — owner/repo.
  TRACKER_BRANCH   (default: main).
  TRACKER_FILE     (default: movements.json) — archivo a tirar del repo.
  MAPPING_FILE     (default: data/random_tracker_mapping.json) — mapping usuario → player_id.
  PUBSUB_TOPIC     (default: player-movements).

CLI override
------------
  --project        — sobreescribe PROJECT_ID.
  --date           — YYYY-MM-DD para backfill de un día anterior.
  --dry-run        — imprime lo que haría sin publicar.
  --local-file     — tira de un JSON local en lugar del repo (para tests).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_mapping(path: Path) -> dict[str, str]:
    """Lee el fichero de mapping usuario → player_id.

    Si el fichero no existe, mapeamos cada entrada del JSON del tracker al
    player demo por defecto (demo-player-001) para que el ingest siga
    funcionando out-of-the-box. En prod este fichero debería rellenarlo Fran
    al dar de alta a los jugadores.
    """
    if not path.exists():
        print(f"[fetcher] mapping file not found ({path}); defaulting everything to demo-player-001")
        return {"*": "demo-player-001"}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fetch_remote_json(repo: str, branch: str, filename: str) -> dict:
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}"
    print(f"[fetcher] GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "cloudrisk-steps-fetcher/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_local_json(path: Path) -> dict:
    print(f"[fetcher] reading local file {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_player_id(mapping: dict[str, str], tracker_user: str | None) -> str:
    if tracker_user and tracker_user in mapping:
        return mapping[tracker_user]
    return mapping.get("*", "demo-player-001")


def estimate_steps_delta(entry: dict, prev: dict | None) -> int:
    """Estimación aproximada: si el tracker trae 'step_count' lo usa; si no,
    lo estima desde velocidad*duración asumiendo un paso de 1.3 m."""
    if "step_count" in entry:
        return int(entry["step_count"])
    # Heurística de fallback
    speed = float(entry.get("speed_mps", 1.3))
    if prev:
        prev_ts = datetime.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
        cur_ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
        duration_s = (cur_ts - prev_ts).total_seconds()
    else:
        duration_s = 60  # asume 1 minuto entre muestras en la primera entrada
    meters = speed * max(duration_s, 0)
    return max(0, int(meters / 0.7))  # 0.7 m por paso (adulto típico)


def dedup_marker(payload: dict, date: str) -> str:
    """Huella estable para poder guardar 'lo que publicamos hoy' y
    saltárnoslo la próxima vez aunque el repo no haya cambiado."""
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{date}-{h}"


def publish_to_pubsub(publisher, topic_path: str, event: dict, dry_run: bool) -> bool:
    data = json.dumps(event).encode("utf-8")
    if dry_run:
        print(f"  [DRY] publish {len(data)}B: {event['player_id']} @ {event['timestamp']} +{event['steps_delta']} steps")
        return True
    future = publisher.publish(topic_path, data)
    future.result(timeout=10)
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=os.environ.get("PROJECT_ID"))
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        help="Día a procesar, YYYY-MM-DD (default: hoy UTC)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local-file", help="Usa este JSON local en vez del repo remoto")
    parser.add_argument("--force", action="store_true", help="Re-publica incluso si ya hay marker de hoy")
    return parser.parse_args()


def _already_published_today(project: str, date: str) -> bool:
    """Devuelve True si Firestore ya tiene marker `step_ingests/{date}`.

    Si el chequeo falla (sin credenciales, Firestore caído), devolvemos
    False y dejamos que el job publique igual — preferimos un duplicado
    ocasional a perder ingesta de un día por un fallo transitorio.
    """
    try:
        from google.cloud import firestore
        db = firestore.Client(project=project)
        marker = db.collection("step_ingests").document(date).get()
        return marker.exists
    except Exception as exc:
        print(f"[fetcher] dedup check falló ({exc}); sigo sin dedup")
        return False


def _load_payload(args: argparse.Namespace, repo: str, branch: str, filename: str) -> dict:
    """Lee el JSON del tracker — fichero local si se pasa `--local-file`,
    si no, GET HTTPS al repo remoto. Aborta con `sys.exit` si falla la red."""
    if args.local_file:
        return fetch_local_json(Path(args.local_file))
    try:
        return fetch_remote_json(repo, branch, filename)
    except Exception as exc:
        sys.exit(f"[fetcher] no pude descargar {repo}/{filename}: {exc}")


def _build_event(movement: dict, payload_user: str | None, mapping: dict[str, str], prev: dict | None) -> dict:
    """Construye el evento CloudRISK a publicar a partir de un movement crudo."""
    tracker_user = movement.get("user") or movement.get("username") or payload_user
    return {
        "player_id":   resolve_player_id(mapping, tracker_user),
        "timestamp":   movement["timestamp"],
        "latitude":    float(movement["latitude"]),
        "longitude":   float(movement["longitude"]),
        "speed_mps":   float(movement.get("speed_mps", 0.0)),
        "steps_delta": estimate_steps_delta(movement, prev),
        "source":      "real",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def _publish_all_movements(payload: dict, mapping: dict[str, str], publisher, topic_path: str, dry_run: bool) -> int:
    """Itera el feed, construye un evento por movement y publica. Devuelve cuántos se publicaron."""
    movements = payload.get("movements", [])
    print(f"[fetcher] {len(movements)} movements en el feed")
    payload_user = payload.get("user")
    published = 0
    prev = None
    for m in movements:
        event = _build_event(m, payload_user, mapping, prev)
        if publish_to_pubsub(publisher, topic_path, event, dry_run):
            published += 1
        prev = m
    return published


def _write_idempotency_marker(project: str, date: str, source_repo: str, published: int) -> None:
    """Escribe `step_ingests/{date}` para que la próxima ejecución lo vea
    y se salte el día (a menos que se pase `--force`)."""
    from google.cloud import firestore
    db = firestore.Client(project=project)
    db.collection("step_ingests").document(date).set({
        "date": date,
        "source_repo": source_repo,
        "published_events": published,
        "finished_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)


def main() -> None:
    args = _parse_args()
    if not args.project:
        sys.exit("[fetcher] --project o PROJECT_ID env var requerido")

    repo = os.environ.get("TRACKER_REPO", "FranciscoAlvarezVaras/random_tracker")
    branch = os.environ.get("TRACKER_BRANCH", "main")
    filename = os.environ.get("TRACKER_FILE", "movements.json")
    topic_name = os.environ.get("PUBSUB_TOPIC", "player-movements")
    mapping_path = Path(os.environ.get("MAPPING_FILE", REPO_ROOT / "data" / "random_tracker_mapping.json"))

    print(f"[fetcher] project={args.project} date={args.date} topic={topic_name} dry={args.dry_run}")

    # 1. Idempotencia: si ya publicamos hoy y no hay --force, salir.
    if not args.force and not args.dry_run and _already_published_today(args.project, args.date):
        print(f"[fetcher] marker step_ingests/{args.date} ya existe. Skip. (use --force para re-publicar)")
        return

    # 2. Carga el payload (remoto o local).
    payload = _load_payload(args, repo, branch, filename)
    mapping = load_mapping(mapping_path)

    # 3. Inicializa publisher (o stub si --dry-run) y publica el feed.
    if args.dry_run:
        publisher, topic_path = None, f"projects/{args.project}/topics/{topic_name}"
    else:
        try:
            from google.cloud import pubsub_v1
        except ImportError:
            sys.exit("[fetcher] pip install google-cloud-pubsub")
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(args.project, topic_name)
    published = _publish_all_movements(payload, mapping, publisher, topic_path, args.dry_run)

    # 4. Persiste el marker de idempotencia (skip en dry-run).
    if not args.dry_run:
        _write_idempotency_marker(args.project, args.date, f"{repo}/{branch}/{filename}", published)

    print(f"[fetcher] OK — publicados {published} events a {topic_path}")


if __name__ == "__main__":
    main()
