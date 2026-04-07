import os
import json
import time
import random
import math
from google.cloud import pubsub_v1
import osmnx as ox
import networkx as nx

PROJECT_ID = os.environ.get("PROJECT_ID", "local-project")
TOPIC_ID = os.environ.get("TOPIC_ID", "user-events")
USER_ID = os.environ.get("USER_ID", "user-001")
INTERVAL_SEC = float(os.environ.get("INTERVAL_SEC", "2"))
WALK_SPEED_MPS = float(os.environ.get("WALK_SPEED_MPS", "1.4"))  # ~5 km/h

# Centro de Valencia + radio en metros
CENTER_LAT = 39.4699
CENTER_LON = -0.3763
RADIUS_M = 1500

# ---------- Pub/Sub ----------
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
try:
    publisher.create_topic(request={"name": topic_path})
    print(f"[walker] Topic creado: {topic_path}")
except Exception:
    print(f"[walker] Topic ya existía: {topic_path}")

# ---------- Cargar grafo de calles ----------
print(f"[walker] Descargando red peatonal de Valencia (radio {RADIUS_M}m)...")
G = ox.graph_from_point((CENTER_LAT, CENTER_LON), dist=RADIUS_M, network_type="walk")
print(f"[walker] Grafo listo: {len(G.nodes)} nodos, {len(G.edges)} aristas")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
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

def publish(event):
    data = json.dumps(event).encode("utf-8")
    future = publisher.publish(topic_path, data)
    print(f"[walker] msg_id={future.result()} {event}")

print(f"[walker] Iniciando paseo de {USER_ID} (intervalo {INTERVAL_SEC}s)")
while True:
    route = random_route()
    for i in range(len(route) - 1):
        n1, n2 = route[i], route[i+1]
        lat1, lon1 = G.nodes[n1]["y"], G.nodes[n1]["x"]
        lat2, lon2 = G.nodes[n2]["y"], G.nodes[n2]["x"]
        dist_m = haversine(lat1, lon1, lat2, lon2)
        # Aproximación de pasos: 1 paso ≈ 0.75 m
        pasos = max(1, int(dist_m / 0.75))
        event = {
            "type": "steps",
            "user_id": USER_ID,
            "ts": int(time.time()),
            "pasos": pasos,
            "lat": lat2,
            "lon": lon2,
            "dist_m": round(dist_m, 2),
        }
        publish(event)
        # Tiempo realista que tardaría andando ese tramo
        sleep_t = max(INTERVAL_SEC, dist_m / WALK_SPEED_MPS)
        time.sleep(sleep_t)
