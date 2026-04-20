"""Turn state + setup + reinforcements endpoints (CloudRISK v3 Clustered Risk)."""
from __future__ import annotations

import json
import math
import os
import random
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from cloudrisk_api.configuracion import settings
from cloudrisk_api.database import usuarios as usuarios_repo, zonas as zonas_repo
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import estado_juego as game_state

USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"


# ─── GeoJSON de Valencia cargado del frontend/public (single source of truth) ──
_GEOJSON_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "valencia_districts.geojson"
if not _GEOJSON_PATH.exists():
    _GEOJSON_PATH = Path("/app/geojson/valencia_districts.geojson")  # Docker mount
_CENTROID_CACHE: dict[str, tuple[float, float]] | None = None


def _slugify(name: str) -> str:
    """Normaliza un nombre de barrio a id tipo 'zona-el-carme'."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("'", "").replace("·", "")
    s = "".join(c if c.isalnum() or c == " " else "" for c in s)
    s = "-".join(s.split())
    return f"zona-{s}"


def _load_centroids() -> dict[str, tuple[float, float]]:
    """Lee el geojson del frontend y devuelve {zone_id: (lat, lng)}."""
    global _CENTROID_CACHE
    if _CENTROID_CACHE is not None:
        return _CENTROID_CACHE
    if not _GEOJSON_PATH.exists():
        return {}
    data = json.loads(_GEOJSON_PATH.read_text(encoding="utf-8"))
    out: dict[str, tuple[float, float]] = {}
    for feat in data.get("features", []):
        name = feat.get("properties", {}).get("name")
        geom = feat.get("geometry") or {}
        if not name or not geom.get("coordinates"):
            continue
        t = geom.get("type")
        if t == "Polygon":
            rings = [geom["coordinates"]]
        elif t == "MultiPolygon":
            rings = geom["coordinates"]
        else:
            continue
        lats, lngs = [], []
        for poly in rings:
            if not poly:
                continue
            for pt in poly[0]:
                if len(pt) >= 2:
                    lngs.append(pt[0])
                    lats.append(pt[1])
        if lats:
            out[_slugify(name)] = (sum(lats) / len(lats), sum(lngs) / len(lngs))
    _CENTROID_CACHE = out
    return out


router = APIRouter(prefix="/turn", tags=["turn"])


# ─── Constants extraídas de settings para claridad ──────────────────────
MIN_ARMIES_PER_ZONE = settings.INITIAL_ARMIES_PER_ZONE   # 2 tropas/zona al setup
STARTING_POOL = settings.STARTING_ARMIES_POOL            # 30 armies iniciales
MIN_TURN_BONUS = settings.MIN_TURN_BONUS                 # 3 armies mínimo por turno
ZONES_PER_BONUS = settings.ZONES_PER_BONUS_ARMY          # 1 army cada 3 zonas

# ─── Clustering parameters ──────────────────────────────────────────────
ZONES_PER_PLAYER_TARGET = 15   # aprox. zonas que recibe cada jugador
MIN_SEED_DISTANCE = 0.03        # ~3 km en grados lat/lng (evitar semillas pegadas)


# ─── Helpers geográficos ────────────────────────────────────────────────

def _zone_centroid(zone: dict) -> tuple[float, float] | None:
    """
    Devuelve el centroide (lat, lng) de una zona.
    Primera intención: usar el geojson embebido. Si está vacío (caso
    in-memory store), cae al cache cargado desde el archivo del frontend.
    """
    geojson = zone.get("geojson")
    if geojson:
        t = geojson.get("type")
        rings = (
            [geojson["coordinates"]] if t == "Polygon"
            else geojson["coordinates"] if t == "MultiPolygon"
            else None
        )
        if rings:
            lats, lngs = [], []
            for poly in rings:
                if not poly:
                    continue
                for pt in poly[0]:
                    if len(pt) >= 2:
                        lngs.append(pt[0])
                        lats.append(pt[1])
            if lats:
                return (sum(lats) / len(lats), sum(lngs) / len(lngs))

    # Fallback: buscar por id en el cache del geojson del frontend
    centroids = _load_centroids()
    return centroids.get(zone["id"])


def _distance(c1: tuple[float, float], c2: tuple[float, float]) -> float:
    return math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2)


def _pick_four_spread_seeds(zones_with_centroid: list[tuple[dict, tuple[float, float]]],
                             rng: random.Random) -> list[dict]:
    """
    Elige 4 semillas (una por jugador) que estén razonablemente separadas.
    Estrategia:
      1. Ordenar todas las zonas por lat (norte → sur).
      2. Tomar muestra aleatoria de los cuartiles norte, sur, este, oeste.
      3. Verificar que las 4 semillas están a mínimo MIN_SEED_DISTANCE entre sí.
      4. Si no, reintentar hasta MAX_RETRIES.
    """
    # Dividir por cuartiles geográficos
    by_lat = sorted(zones_with_centroid, key=lambda x: x[1][0])   # sur → norte
    by_lng = sorted(zones_with_centroid, key=lambda x: x[1][1])   # oeste → este
    n = len(by_lat)

    # Cuartiles: norte = último 25%, sur = primero 25%, este = último 25% por lng, etc.
    norte_pool = by_lat[int(n * 0.75):]    # lat alta
    sur_pool   = by_lat[:int(n * 0.25)]    # lat baja
    este_pool  = by_lng[int(n * 0.75):]    # lng alta (este es lng +)
    oeste_pool = by_lng[:int(n * 0.25)]    # lng baja

    for _ in range(50):  # reintentos
        seeds = [
            rng.choice(norte_pool),
            rng.choice(sur_pool),
            rng.choice(este_pool),
            rng.choice(oeste_pool),
        ]
        # dedup por id — puede que una zona caiga en dos cuartiles
        seen: set[str] = set()
        unique_seeds: list[tuple[dict, tuple[float, float]]] = []
        for s in seeds:
            if s[0]["id"] not in seen:
                seen.add(s[0]["id"])
                unique_seeds.append(s)
        if len(unique_seeds) < 4:
            continue
        # verificar separación mínima
        ok = True
        for i in range(len(unique_seeds)):
            for j in range(i + 1, len(unique_seeds)):
                if _distance(unique_seeds[i][1], unique_seeds[j][1]) < MIN_SEED_DISTANCE:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return [z for z, _ in unique_seeds]

    # Fallback: si no encontramos buenas semillas, usa las 4 más separadas posibles
    return [by_lat[-1][0], by_lat[0][0], by_lng[-1][0], by_lng[0][0]]


# ─── Business logic helpers ─────────────────────────────────────────────

def _compute_zone_bonus(player_id: str) -> tuple[int, int]:
    """max(MIN, zones_owned // ZONES_PER_BONUS). Risk rule."""
    zones = zonas_repo.list_zones()
    owned = sum(1 for z in zones if z.get("owner_clan_id") == player_id)
    bonus = max(MIN_TURN_BONUS, owned // ZONES_PER_BONUS)
    return bonus, owned


def _grant_turn_bonus(player_id: str) -> dict:
    """Acredita al jugador sus refuerzos de turno como power_points."""
    bonus, owned = _compute_zone_bonus(player_id)
    user = usuarios_repo.get_user_by_id(player_id) or {}
    current = int(user.get("power_points") or 0)
    new_power = current + bonus
    usuarios_repo.update_user(player_id, {"power_points": new_power})
    return {"bonus_armies": bonus, "zones_owned": owned,
            "power_before": current, "power_after": new_power}


# ─── Endpoints ──────────────────────────────────────────────────────────

@router.get("/")
def get_turn():
    """Estado del turno actual. Frontend lo pollea cada pocos segundos."""
    return game_state.current().to_dict()


@router.get("/reinforcements")
def reinforcements(current_user: dict = Depends(get_current_user)):
    """
    Explica el cálculo de refuerzos del jugador autenticado.
    Útil para que el frontend muestre un desglose tipo:
        "Tienes 27 armies: 7 por 22 zonas + 20 por 10k pasos."
    """
    bonus, owned = _compute_zone_bonus(current_user["id"])
    steps = int(current_user.get("steps_total") or 0)
    power_points = int(current_user.get("power_points") or 0)
    return {
        "available_now": power_points,
        "next_turn_zone_bonus": bonus,
        "zones_owned": owned,
        "total_steps": steps,
        "formula": {
            "zone_bonus": f"max({MIN_TURN_BONUS}, {owned}/{ZONES_PER_BONUS}) = {bonus}",
            "steps_to_armies": f"1 army cada {settings.POWER_PER_STEPS} pasos",
        },
    }


@router.post("/advance_phase")
def advance_phase(current_user: dict = Depends(get_current_user)):
    """Avanza a la siguiente fase del turno (reinforce → attack → fortify)."""
    state = game_state.current()
    if state.current_player_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="It's not your turn")
    return game_state.advance_phase().to_dict()


@router.post("/end")
def end_turn(current_user: dict = Depends(get_current_user)):
    """
    Termina tu turno. El jugador ACTUAL recibe sus refuerzos (por las zonas
    que controla ahora) y luego el turno pasa al siguiente.

    Fix: antes se daba el bonus al SIGUIENTE jugador en lugar de al actual,
    así que el humano nunca recibía sus tropas y los bots las recibían doble.
    """
    state = game_state.current()
    if state.current_player_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="It's not your turn")
    bonus_info = _grant_turn_bonus(current_user["id"])
    new_state = game_state.end_turn()
    return {**new_state.to_dict(), "bonus_granted": bonus_info}


# ─── CloudRISK v3 setup — "Clustered Risk" rules ────────────────────────


def _compute_zones_with_centroid(zones: list[dict]) -> list[tuple[dict, tuple[float, float]]]:
    """Filtra las zonas que tienen geojson válido y devuelve `(zone, centroid)`.

    Las zonas sin centroide computable (sin geometría) quedan fuera; el caller
    las marcará como libres más tarde para no perderlas.
    """
    result: list[tuple[dict, tuple[float, float]]] = []
    for z in zones:
        c = _zone_centroid(z)
        if c is None:
            continue
        result.append((z, c))
    return result


def _assign_zones_to_players(
    zones_with_centroid: list[tuple[dict, tuple[float, float]]],
    seeds: list[dict],
    order: list[str],
) -> tuple[dict[str, list[str]], set[str]]:
    """Asigna `ZONES_PER_PLAYER_TARGET` zonas a cada jugador en round-robin
    greedy por proximidad a su semilla.

    Devuelve `(assignments, taken)` donde:
      - `assignments[player_id]` = lista de zona_ids (incluye su semilla).
      - `taken` = set con todas las zona_ids ya asignadas (para diferenciar
        las que quedan libres por estar fuera del cluster).
    """
    seed_centroids = [_zone_centroid(s) for s in seeds]
    seed_owners = dict(zip(order, seeds))    # player_id → seed zone
    seed_ids = {s["id"] for s in seeds}

    # Para cada jugador, lista priorizada de candidatos (zonas no-semilla
    # ordenadas de más cercana a más lejana a su semilla).
    candidates: dict[int, list[tuple[float, str]]] = {i: [] for i in range(len(order))}
    for zone, centroid in zones_with_centroid:
        if zone["id"] in seed_ids:
            continue
        for player_idx in range(len(order)):
            dist = _distance(centroid, seed_centroids[player_idx])
            candidates[player_idx].append((dist, zone["id"]))
    for pidx in candidates:
        candidates[pidx].sort()

    assignments: dict[str, list[str]] = {p: [seed_owners[p]["id"]] for p in order}
    taken: set[str] = {seed_owners[p]["id"] for p in order}
    progress = [0] * len(order)   # puntero por jugador dentro de su lista de candidatos

    # Round-robin: cada jugador toma su siguiente candidato no asignado hasta
    # llegar al target o agotarse los candidatos.
    target = ZONES_PER_PLAYER_TARGET
    repartiendo = True
    while repartiendo:
        repartiendo = False
        for pidx, player_id in enumerate(order):
            if len(assignments[player_id]) >= target:
                continue
            while progress[pidx] < len(candidates[pidx]):
                _, zid = candidates[pidx][progress[pidx]]
                progress[pidx] += 1
                if zid not in taken:
                    assignments[player_id].append(zid)
                    taken.add(zid)
                    repartiendo = True
                    break

    return assignments, taken


def _apply_zone_assignments(
    assignments: dict[str, list[str]],
    free_ids: set[str],
):
    """Persiste el setup: zonas asignadas con su owner + garrison mínimo,
    zonas libres con `owner_clan_id=None`."""
    now_iso = datetime.now(timezone.utc).isoformat()
    for player_id, zone_ids in assignments.items():
        for zone_id in zone_ids:
            zonas_repo.update_zone(zone_id, {
                "owner_clan_id": player_id,
                "defense_level": MIN_ARMIES_PER_ZONE,
                "conquered_at": now_iso,
            })
    for zid in free_ids:
        zonas_repo.update_zone(zid, {
            "owner_clan_id": None,
            "defense_level": 0,
            "conquered_at": None,
        })


def _run_setup() -> dict:
    """Núcleo del setup — idempotente, sin auth. Devuelve el mismo dict que
    el endpoint. Reutilizable desde:
      - `POST /turn/setup` (trigger manual / scheduler).
      - `ensure_game_setup()` (auto-arranque del backend en local).

    Raises `RuntimeError` si no hay zonas sembradas o hay menos de 10 con
    geojson — el llamador decide si convertirlo en 500 o en log+skip.
    """
    zones = zonas_repo.list_zones()
    if not zones:
        raise RuntimeError("No zones seeded")

    zones_with_centroid = _compute_zones_with_centroid(zones)
    if len(zones_with_centroid) < 10:
        raise RuntimeError(
            f"Too few zones with geojson to cluster ({len(zones_with_centroid)})"
        )

    rng = random.Random()
    seeds = _pick_four_spread_seeds(zones_with_centroid, rng)
    order = game_state.DEFAULT_PLAYER_ORDER
    seed_owners = dict(zip(order, seeds))

    assignments, taken = _assign_zones_to_players(zones_with_centroid, seeds, order)

    all_cluster_ids = {z["id"] for z, _ in zones_with_centroid}
    all_db_ids = {z["id"] for z in zones}
    free_in_cluster = all_cluster_ids - taken
    free_no_geo = all_db_ids - all_cluster_ids
    free_ids = free_in_cluster | free_no_geo

    _apply_zone_assignments(assignments, free_ids)

    for pid in order:
        usuarios_repo.update_user(pid, {"power_points": STARTING_POOL})

    game_state.reset()

    return {
        "status": "ok",
        "rule": "CloudRISK v3 · Clustered Risk — territorios cercanos + zonas libres",
        "setup": {
            "zones_per_player": {p: len(v) for p, v in assignments.items()},
            "free_zones_total": len(free_ids),
            "free_by_cluster_miss": len(free_in_cluster),
            "free_by_no_geojson":   len(free_no_geo),
            "total_zones_in_db":     len(zones),
            "armies_per_owned_zone": MIN_ARMIES_PER_ZONE,
            "starting_pool_per_player": STARTING_POOL,
            "seeds": {p: seed_owners[p]["id"] for p in order},
        },
        "per_turn_formula": {
            "zone_bonus": f"max({MIN_TURN_BONUS}, zones/{ZONES_PER_BONUS})",
            "step_bonus": f"floor(steps / {settings.POWER_PER_STEPS})",
        },
        "starts": order[0],
        "phase": "reinforce",
    }


def ensure_game_setup() -> dict | None:
    """Dispara el setup si detecta que la partida está 'cruda' (ninguna zona
    tiene owner). Pensado para llamarse una vez al arrancar el backend en
    local — en prod el scheduler tiene su propio trigger vía /turn/setup.
    Devuelve el resultado del setup si lo ejecutó, `None` si ya estaba listo.
    """
    try:
        zones = zonas_repo.list_zones()
        if any(z.get("owner_clan_id") for z in zones):
            return None
        return _run_setup()
    except Exception as e:
        # El seed de zonas puede llegar milisegundos después si hay carrera
        # entre el lifespan y la primera request; no queremos tumbar el API.
        print(f"[SETUP] Auto-setup skipped: {e}")
        return None


@router.post("/setup", tags=["setup"])
def setup_game(
    x_scheduler_token: Optional[str] = Header(None, alias="X-Scheduler-Token"),
    current_user: dict = Depends(get_current_user),
):
    """
    Fase de preparación v3 (Clustered Risk).

    Pasos:
        1. Calcula el centroide (lat, lng) de cada zona desde su geojson.
        2. Elige 4 semillas geográficamente SEPARADAS (una norte, sur,
           este, oeste) — son los centros iniciales de cada jugador.
        3. Para cada zona no-semilla, encuentra su semilla más cercana.
           Asigna las ZONES_PER_PLAYER_TARGET (15) zonas más cercanas a
           cada semilla. Las demás quedan LIBRES (owner_clan_id=None,
           defense_level=0).
        4. Coloca MIN_ARMIES_PER_ZONE armies en cada zona asignada.
           Las libres se quedan a 0 armies (se reclaman con /actions/place).
        5. Cada jugador recibe STARTING_POOL (30) armies como power_points
           para desplegar donde quiera (reforzar o reclamar zonas libres).
           15 zonas × 2 tropas + 30 pool = 60 armies iniciales por jugador.
        6. Resetea el turno: Norte, fase reinforce, turno 1.

    Resultado: ~60 zonas repartidas (15 por jugador, clusterizadas) +
    ~26 zonas libres que cualquiera puede reclamar en su turno.

    Seguridad: fuera de USE_LOCAL_STORE=1 el endpoint exige también
    X-Scheduler-Token (Cloud Scheduler / ops) para evitar que cualquier
    jugador autenticado resetee la partida en demo/producción.
    """
    if not USE_LOCAL and x_scheduler_token != settings.SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: scheduler token required")
    try:
        return _run_setup()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
