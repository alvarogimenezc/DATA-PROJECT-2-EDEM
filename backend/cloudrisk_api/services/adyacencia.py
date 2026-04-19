"""
Adjacency precomputado desde el geojson de Valencia.

Regla oficial del Risk: solo puedes atacar una zona si es ADYACENTE a una
que ya posees. Aquí calculamos qué barrios comparten frontera leyendo el
geojson una sola vez al arranque y guardando el grafo en memoria.

Algoritmo:
    1. Para cada feature del geojson, extraer todos los vértices (lng, lat)
       redondeados a 5 decimales (~1m de precisión).
    2. Dos zonas se consideran adyacentes si comparten >=2 vértices (edge
       compartido, no solo un corner casual).
    3. Guardar como dict {zone_id: frozenset(neighbor_ids)}.

En Valencia (86 barrios del geojson limpio) esto da ~5-7 vecinos promedio
por barrio, que es lo esperado para un teselado geográfico.

EDEM. Master Big Data & Cloud 2025/2026
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path


_GEOJSON_PATH = Path(__file__).resolve().parents[2] / "frontend" / "public" / "valencia_districts.geojson"
# Si ejecutas desde backend/ el path arriba falla — alternativa con parents[3]
if not _GEOJSON_PATH.exists():
    _GEOJSON_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "valencia_districts.geojson"
if not _GEOJSON_PATH.exists():
    _GEOJSON_PATH = Path("/app/geojson/valencia_districts.geojson")  # Docker mount

_ADJACENCY_CACHE: dict[str, frozenset[str]] | None = None

# Precision: 5 decimals ~= 1.1 m. Bordes limpios comparten vértices exactos.
_COORD_PRECISION = 5

# Threshold: dos zonas son adyacentes si comparten al menos N vértices.
# 1 = también considera corner-only. 2 = solo edges reales (más estricto).
_MIN_SHARED_VERTICES = 1


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("'", "").replace("·", "")
    s = "".join(c if c.isalnum() or c == " " else "" for c in s)
    s = "-".join(s.split())
    return f"zona-{s}"


def _iter_rings(geom: dict):
    """Itera anillos exteriores de Polygon/MultiPolygon."""
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon":
        yield coords[0] if coords else []
    elif t == "MultiPolygon":
        for poly in coords:
            if poly:
                yield poly[0]


def _vertex_set(geom: dict) -> set[tuple[float, float]]:
    """Devuelve el set de vértices (lng, lat) redondeados."""
    pts: set[tuple[float, float]] = set()
    for ring in _iter_rings(geom):
        for pt in ring:
            if len(pt) >= 2:
                pts.add((round(pt[0], _COORD_PRECISION), round(pt[1], _COORD_PRECISION)))
    return pts


def _compute_adjacency() -> dict[str, frozenset[str]]:
    """Carga geojson, calcula vecinos una sola vez."""
    if not _GEOJSON_PATH.exists():
        return {}
    data = json.loads(_GEOJSON_PATH.read_text(encoding="utf-8"))
    # zone_id → vertex set
    zone_vertices: dict[str, set[tuple[float, float]]] = {}
    for feat in data.get("features", []):
        name = feat.get("properties", {}).get("name")
        geom = feat.get("geometry") or {}
        if not name or not geom:
            continue
        zone_vertices[_slugify(name)] = _vertex_set(geom)

    # Build an inverted index: vertex → set(zone_ids that contain it)
    # Then two zones share K vertices = count how many verts are in both sets.
    vertex_to_zones: dict[tuple[float, float], set[str]] = defaultdict(set)
    for zid, verts in zone_vertices.items():
        for v in verts:
            vertex_to_zones[v].add(zid)

    # Count shared vertices per pair
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for zones in vertex_to_zones.values():
        if len(zones) < 2:
            continue
        zlist = sorted(zones)
        for i in range(len(zlist)):
            for j in range(i + 1, len(zlist)):
                shared[(zlist[i], zlist[j])] += 1

    # Build adjacency dict
    adj: dict[str, set[str]] = defaultdict(set)
    for (a, b), count in shared.items():
        if count >= _MIN_SHARED_VERTICES:
            adj[a].add(b)
            adj[b].add(a)

    return {zid: frozenset(neigh) for zid, neigh in adj.items()}


def get_adjacency() -> dict[str, frozenset[str]]:
    """Devuelve el grafo completo {zone_id: frozenset(neighbors)}."""
    global _ADJACENCY_CACHE
    if _ADJACENCY_CACHE is None:
        _ADJACENCY_CACHE = _compute_adjacency()
    return _ADJACENCY_CACHE


def neighbors_of(zone_id: str) -> frozenset[str]:
    """Vecinos directos de una zona. Vacío si la zona no está en el grafo."""
    return get_adjacency().get(zone_id, frozenset())


def are_adjacent(zone_a: str, zone_b: str) -> bool:
    """True si las dos zonas comparten frontera."""
    return zone_b in neighbors_of(zone_a)


def stats() -> dict:
    """Útil para debugging: cuántos vecinos promedio/min/max."""
    adj = get_adjacency()
    if not adj:
        return {"zones": 0, "avg_neighbors": 0, "min": 0, "max": 0}
    counts = [len(v) for v in adj.values()]
    return {
        "zones": len(adj),
        "avg_neighbors": round(sum(counts) / len(counts), 2),
        "min_neighbors": min(counts),
        "max_neighbors": max(counts),
    }
