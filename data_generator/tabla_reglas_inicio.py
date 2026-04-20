from __future__ import annotations

import requests


# Reglas del juego — deben coincidir con backend/cloudrisk_api/configuracion.py
MIN_ARMIES_PER_ZONE = 2
STARTING_POOL = 30
STEPS_PER_ARMY = 500


def _get(api: str, path: str, token: str | None = None) -> dict | list:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(f"{api}{path}", headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()


def _post(api: str, path: str, token: str) -> dict:
    r = requests.post(
        f"{api}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _zones_owned(zones: list[dict], player_id: str) -> int:
    return sum(
        1 for z in zones
        if (z.get("owner_clan_id") or z.get("owner")) == player_id
    )


def _steps_today(api: str, token: str, fallback_total: int) -> int:
    # Intenta obtener los pasos reales de hoy. Si no hay conexión, usa el total histórico como aproximación.
    try:
        data = _get(api, "/api/v1/steps/realtime-ingestion-status", token)
        today = int(data.get("today_real_steps") or 0)
        return today if today > 0 else fallback_total
    except Exception:
        return fallback_total


def mostrar_tabla_reglas(api: str, tokens: dict[str, dict]) -> None:
    # 1. Configuración inicial del tablero (solo necesita un jugador logueado).
    # Fase 1 — setup idempotente. Basta con un jugador autenticado.
    any_token = next(iter(tokens.values()))["token"]
    try:
        setup = _post(api, "/api/v1/turn/setup", any_token)
    except requests.HTTPError as exc:
        print(f"[tabla_reglas] No se pudo invocar /turn/setup: {exc}")
        setup = {}

    # Fase 2 — obtener estado por jugador.
    zones = _get(api, "/api/v1/zones/")

    filas: list[tuple[str, int, int, int, int, int]] = []
    for pid, info in tokens.items():
        tok = info["token"]
        me = _get(api, "/api/v1/users/me", tok)
        steps_total = int(me.get("steps_total") or 0)
        steps_hoy = _steps_today(api, tok, steps_total)
        zonas = _zones_owned(zones, pid)
        from_zones = zonas * MIN_ARMIES_PER_ZONE
        from_pool = STARTING_POOL
        from_steps = steps_hoy // STEPS_PER_ARMY
        total = from_zones + from_pool + from_steps
        filas.append((info.get("name", pid), zonas, from_zones, from_pool, from_steps, total))

    # Fase 3 — render
    print()
    print("=" * 78)
    print("  CLOUDRISK - REGLAS DE INICIO DE PARTIDA")
    print("=" * 78)
    print("  Formula: tropas_iniciales = zonas x 2  +  30 (pool)  +  pasos_hoy / 500")
    print(f"  - {MIN_ARMIES_PER_ZONE} tropas por barrio propio (desplegadas por el setup)")
    print(f"  - {STARTING_POOL} tropas de pool para colocar libremente")
    print(f"  - 1 tropa extra por cada {STEPS_PER_ARMY} pasos del dia")
    if setup.get("setup", {}).get("free_zones_total") is not None:
        libres = setup["setup"]["free_zones_total"]
        total_db = setup["setup"].get("total_zones_in_db", "?")
        print(f"  - Zonas libres en el mapa: {libres} / {total_db}  (reclamables con /place)")
    print("-" * 78)
    print(f"  {'Jugador':<10} {'Zonas':>6} {'x2':>6} {'+Pool':>7} {'+Pasos':>8} {'= Total':>10}")
    print("-" * 78)
    for name, zonas, fz, fp, fs, total in filas:
        print(f"  {name:<10} {zonas:>6d} {fz:>6d} {fp:>7d} {fs:>8d} {total:>10d}")
    print("=" * 78)
    print()
