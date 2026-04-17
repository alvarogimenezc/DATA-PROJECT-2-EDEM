# ============================================================
# data_generator/main.py
# Walker CloudRISK: simula un jugador caminando por Valencia
# y publica sus posiciones al topic player-movements de Pub/Sub.
#
# Publica al proyecto GCP REAL (no emulador). Necesita que el
# contenedor tenga montadas las credenciales ADC en
# /tmp/adc.json y la env var GOOGLE_APPLICATION_CREDENTIALS.
# ============================================================

import os
import json
import time
import random
import math
from datetime import datetime, timezone
from google.cloud import pubsub_v1
import osmnx as ox
import networkx as nx

# ----- Config vía variables de entorno -----
PROJECT_ID = os.environ.get("PROJECT_ID", "cloudrisk-492619")
TOPIC_ID = os.environ.get("TOPIC_ID", "player-movements")
PLAYER_ID = os.environ.get("PLAYER_ID", "player_001")
WALK_SPEED_MPS = float(os.environ.get("WALK_SPEED_MPS", "1.4"))  # ~5 km/h
MIN_INTERVAL_SEC = float(os.environ.get("MIN_INTERVAL_SEC", "1"))

# Centro Valencia + radio en metros
CENTER_LAT = 39.4699
CENTER_LON = -0.3763
RADIUS_M = 1500

# ----- Pub/Sub -----
# Asume que el topic ya existe en GCP (lo creamos con gcloud).
# Si no existe, el publish dará error y el script morirá -> mejor que silencioso.
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
print(f"[walker] Publicando a {topic_path}")

# ----- Cargar grafo de calles peatonales de Valencia -----
print(f"[walker] Descargando red peatonal de Valencia (radio {RADIUS_M}m)...")
G = ox.graph_from_point((CENTER_LAT, CENTER_LON), dist=RADIUS_M, network_type="walk")
print(f"[walker] Grafo listo: {len(G.nodes)} nodos, {len(G.edges)} aristas")


def haversine(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos puntos lat/lon."""
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def random_route():
    """Devuelve una lista de nodos: ruta aleatoria entre dos puntos del grafo."""
    while True:
        orig = random.choice(list(G.nodes))
        dest = random.choice(list(G.nodes))
        if orig == dest:
            continue
        try:
            return nx.shortest_path(G, orig, dest, weight="length")
        except nx.NetworkXNoPath:
            continue


def publish_movement(lat: float, lon: float, speed_mps: float):
    """Publica un evento de movimiento al topic player-movements
    con el esquema oficial de WalkRisk."""
    event = {
        "player_id": PLAYER_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": lat,
        "longitude": lon,
        "speed_mps": speed_mps,
    }
    data = json.dumps(event).encode("utf-8")
    future = publisher.publish(topic_path, data)
    print(f"[walker] msg_id={future.result()} {event}")


print(f"[walker] Iniciando paseo de {PLAYER_ID} a {WALK_SPEED_MPS} m/s")
while True:
    route = random_route()
    for i in range(len(route) - 1):
        n1, n2 = route[i], route[i + 1]
        lat1, lon1 = G.nodes[n1]["y"], G.nodes[n1]["x"]
        lat2, lon2 = G.nodes[n2]["y"], G.nodes[n2]["x"]
        dist_m = haversine(lat1, lon1, lat2, lon2)
        # Tiempo realista que tardaría andando ese tramo
        sleep_t = max(MIN_INTERVAL_SEC, dist_m / WALK_SPEED_MPS)
        publish_movement(lat2, lon2, WALK_SPEED_MPS)
        time.sleep(sleep_t)
