#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from tabla_reglas_inicio import mostrar_tabla_reglas

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("juego_caminante")

API = os.environ.get("API_BASE", "http://127.0.0.1:8080")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")

# Configuración de Pub/Sub
PUBSUB_PROJECT = os.environ.get("PUBSUB_PROJECT")
PUBSUB_TOPIC_MOVEMENTS = os.environ.get("PUBSUB_TOPIC_MOVEMENTS", "player-movements")
_publisher = None
_topic_path = None


def _get_publisher():


    global _publisher, _topic_path
    if _publisher is not None:
        return _publisher, _topic_path
    if not PUBSUB_PROJECT:
        return None, None
    try:
        from google.cloud import pubsub_v1
        _publisher = pubsub_v1.PublisherClient()
        _topic_path = _publisher.topic_path(PUBSUB_PROJECT, PUBSUB_TOPIC_MOVEMENTS)
    except Exception as exc:
        log.warning(f"Pub/Sub disabled: {exc}")
        _publisher, _topic_path = None, None
    return _publisher, _topic_path


def publish_movement(player_id: str, lat: float, lng: float, speed_mps: float = 1.3):


    pub, topic = _get_publisher()
    if not pub:
        return
    payload = json.dumps({
        "player_id": player_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": lat,
        "longitude": lng,
        "speed_mps": round(float(speed_mps), 3),
    }).encode("utf-8")
    try:
        pub.publish(topic, payload)
    except Exception as exc:
        log.warning(f"publish to {PUBSUB_TOPIC_MOVEMENTS} failed: {exc}")

PLAYERS = [
    ("demo-player-001", "Norte",  "norte@cloudrisk.app"),
    ("demo-player-002", "Sur",    "sur@cloudrisk.app"),
    ("demo-player-003", "Este",   "este@cloudrisk.app"),
    ("demo-player-004", "Oeste",  "oeste@cloudrisk.app"),
]
NAMES = {pid: name for pid, name, _ in PLAYERS}

# Límites del mapa de Valencia y tamaño de paso
LAT_MIN, LAT_MAX = 39.440, 39.510
LNG_MIN, LNG_MAX = -0.420, -0.310
STEP = 0.006  


def _centroid(coords) -> tuple[float, float] | None:

    def _extract_polygons(geom):
        t = geom.get("type")
        if t == "Polygon":
            return [geom["coordinates"]]
        if t == "MultiPolygon":
            return geom["coordinates"]
        return []

    all_rings = _extract_polygons(coords)
    if not all_rings:
        return None
    lats, lngs = [], []
    for rings in all_rings:
        outer = rings[0]   # first ring is the outer boundary
        for lng, lat in outer:
            lats.append(lat)
            lngs.append(lng)
    if not lats:
        return None
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))


def load_zone_centroids() -> dict[str, tuple[float, float]]:

    geojson_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "valencia_districts.geojson"
    if not geojson_path.exists():
        sys.exit(f"GeoJSON not found at {geojson_path}")
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    out = {}
    for feat in gj.get("features", []):
        name = (feat.get("properties") or {}).get("name")
        if not name:
            continue
        c = _centroid(feat.get("geometry") or {})
        if c:
            out[name.lower()] = c
    return out


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371000
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def login_all() -> dict[str, dict]:
    tokens = {}
    for pid, name, email in PLAYERS:
        r = requests.post(
            f"{API}/api/v1/users/login",
            data={"username": email, "password": PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        r.raise_for_status()
        body = r.json()
        tokens[pid] = {"token": body["access_token"], "email": email, "name": name}
    return tokens


def bootstrap_power(tokens: dict):
    for info in tokens.values():
        requests.post(f"{API}/api/v1/steps/sync",
                      json={"steps": 10000},
                      headers={"Authorization": f"Bearer {info['token']}"},
                      timeout=5)


def zones_snapshot() -> list[dict]:
    return requests.get(f"{API}/api/v1/zones/", timeout=5).json()


def nearest_zone(walker: tuple[float, float], zones: list[dict],
                 centroids: dict[str, tuple[float, float]]) -> dict | None:
    """Return the zone whose centroid is closest to the walker."""
    best = None
    best_d = float("inf")
    for z in zones:
        c = centroids.get(z["name"].lower())
        if not c:
            continue
        d = haversine_m(walker, c)
        if d < best_d:
            best_d = d
            best = z
    return best


def drift(point: tuple[float, float], rng: random.Random) -> tuple[float, float]:
    lat = max(LAT_MIN, min(LAT_MAX, point[0] + rng.uniform(-STEP, STEP)))
    lng = max(LNG_MIN, min(LNG_MAX, point[1] + rng.uniform(-STEP, STEP)))
    return (lat, lng)


def post(path: str, token: str, **body):
    return requests.post(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, json=body or None, timeout=5)


def act_walker(pid: str, info: dict, walker: tuple[float, float], zones: list[dict], centroids: dict) -> str:
    tok = info["token"]
    me_power = int(requests.get(f"{API}/api/v1/users/me", headers={"Authorization": f"Bearer {tok}"}, timeout=5).json().get("power_points") or 0)
    
    # Recarga automática si el jugador se queda sin pasos
    if me_power < 5:
        post("/api/v1/steps/sync", tok, steps=5000)
        me_power = int(requests.get(f"{API}/api/v1/users/me", headers={"Authorization": f"Bearer {tok}"}, timeout=5).json().get("power_points") or 0)

    target = nearest_zone(walker, zones, centroids)
    if not target:
        return "no zone near walker"

    owner = target.get("owner_clan_id") or target.get("owner")
    tname = target["name"]

    if not owner and me_power >= 1:
        amt = min(me_power, 5)
        post("/api/v1/armies/place", tok, location_id=target["id"], amount=amt)
        return f"CLAIM  {tname:22s} +{amt}"

    if owner == pid and me_power >= 1:
        amt = min(me_power, 3)
        post("/api/v1/armies/place", tok, location_id=target["id"], amount=amt)
        return f"REINF  {tname:22s} +{amt}"

    if owner and owner != pid:
       
        owned = [z for z in zones if (z.get("owner_clan_id") or z.get("owner")) == pid
                 and int(z.get("defense_level") or 0) >= 2]
        if not owned:
            return f"ATK?   need own zone to attack {tname}"
        source = min(owned, key=lambda z: haversine_m(walker, centroids.get(z["name"].lower(), walker)))
        dice = min(3, int(source.get("defense_level") or 2) - 1)
        if dice < 1:
            return "ATK?   source too thin"
        r = post(f"/api/v1/zones/{target['id']}/attack",
                 tok, from_zone_id=source["id"], attacker_dice=dice)
        if r.status_code == 200:
            j = r.json()
            tag = "CONQ!" if j["conquered"] else "def. "
            return (f"ATK    {tag} {source['name']} → {tname}  "
                    f"{j['attacker_rolls']} vs {j['defender_rolls']} "
                    f"(-{j['attacker_losses']}/-{j['defender_losses']})")
        return f"ATK    FAIL {r.status_code}"

    return "idle"


def print_standings(move: int, zones: list[dict]):
    owned = Counter((z.get("owner_clan_id") or z.get("owner")) for z in zones
                    if (z.get("owner_clan_id") or z.get("owner")))
    total = sum(owned.values())
    print(f"\n─── move {move} │ {total}/{len(zones)} conquered ───")
    for pid, _, _ in PLAYERS:
        n = owned.get(pid, 0)
        bar = "#" * min(n, 40)
        print(f"  {NAMES[pid]:6s} {n:3d}  {bar}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--moves", type=int, default=300)
    p.add_argument("--pause", type=float, default=0.12, help="Seconds between moves.")
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()


def _bootstrap(args: argparse.Namespace, rng: random.Random):

    centroids = load_zone_centroids()
    print(f"Loaded {len(centroids)} zone centroids from GeoJSON.")

    tokens = login_all()
    bootstrap_power(tokens)
    print(f"Logged in: {', '.join(i['name'] for i in tokens.values())}  (+10k steps each)\n")

    # Nueva partida → setup + tabla de reglas (2 tropas/barrio + 30 pool + pasos del día)
    mostrar_tabla_reglas(API, tokens)

    walkers = {pid: (rng.uniform(LAT_MIN, LAT_MAX), rng.uniform(LNG_MIN, LNG_MAX))
               for pid, _, _ in PLAYERS}
    for pid, w in walkers.items():
        print(f"  {NAMES[pid]:6s} starts at ({w[0]:.4f}, {w[1]:.4f})")
    print()

    return tokens, centroids, walkers


def _game_loop(args: argparse.Namespace, rng: random.Random, tokens, centroids, walkers):

    for move in range(1, args.moves + 1):
        turn = requests.get(f"{API}/api/v1/turn/", timeout=5).json()
        pid = turn["current_player_id"]
        if pid not in tokens:
            print(f"unknown player_id {pid}, stopping")
            break

        walkers[pid] = drift(walkers[pid], rng)
        zones = zones_snapshot()
        note = act_walker(pid, tokens[pid], walkers[pid], zones, centroids)
        w = walkers[pid]
        print(f"move {move:3d}  {NAMES[pid]:6s}  walker=({w[0]:.4f},{w[1]:.4f})  {note}")

        
        walk_speed = STEP * 111_000 / max(0.001, args.pause)  # ° → m / s
        publish_movement(pid, w[0], w[1], speed_mps=min(walk_speed, 2.5))

        post("/api/v1/turn/end", tokens[pid]["token"])

        if move % 25 == 0:
            print_standings(move, zones)

        time.sleep(args.pause)


def main():
    args = _parse_args()
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    tokens, centroids, walkers = _bootstrap(args, rng)
    _game_loop(args, rng, tokens, centroids, walkers)
    print_standings(args.moves, zones_snapshot())


if __name__ == "__main__":
    main()
