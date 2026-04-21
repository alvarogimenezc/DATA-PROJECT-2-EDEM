#!/usr/bin/env python3
#Script para inicializar la base de datos (Firestore) y Pub/Sub con datos de prueba.
#Prepara el juego con 4 jugadores, 87 zonas y algunas batallas de ejemplo para la demo.
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fuerza stdout UTF-8 en todas partes (el cp1252 de Windows se atraganta con ━ ✓ → ✗).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
STATE_JSON = REPO_ROOT / "data" / "demo_game_state.json"


# ---------------------------------------------------------------------------
# Impresión a color que funciona en Windows sin necesidad de colorama
# ---------------------------------------------------------------------------
def _enable_windows_ansi() -> None:
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


_enable_windows_ansi()

GREEN = "\033[32m"
RED = "\033[31m"
BLUE = "\033[34m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {BLUE}→{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {RED}!{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{BLUE}━━ {title} ━━{RESET}")


# ---------------------------------------------------------------------------
# Cargadores de datos
# ---------------------------------------------------------------------------
def load_players_basic() -> list[dict]:
    if not PLAYERS_JSON.exists():
        sys.exit(f"[demo] players file not found: {PLAYERS_JSON}")
    with PLAYERS_JSON.open(encoding="utf-8") as f:
        return json.load(f).get("players", [])


def load_demo_state() -> dict:
    if not STATE_JSON.exists():
        sys.exit(f"[demo] demo state file not found: {STATE_JSON}")
    with STATE_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def load_zones() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from cloudrisk_api.database.almacen_en_memoria import VALENCIA_ZONES  # type: ignore
    return list(VALENCIA_ZONES)


# ---------------------------------------------------------------------------
# Escribe todo a Firestore
# ---------------------------------------------------------------------------
def _build_owner_map(zone_ownership: dict, zones: list[dict]) -> dict[str, tuple[str, str, int]]:
    """Aplana `zone_ownership` (estructura por owner) en un mapa
    `zone_id → (owner_id, color, armies)`. Salta zonas que no existen en
    `VALENCIA_ZONES` y entradas de metadatos (`_comment`)."""
    valid = {z["id"] for z in zones}
    owner_by_zone: dict[str, tuple[str, str, int]] = {}
    for owner_id, blob in zone_ownership.items():
        if owner_id.startswith("_") or not isinstance(blob, dict):
            continue
        color = blob["color"]
        armies = blob["armies_per_zone"]
        for z in blob["zones"]:
            if z not in valid:
                warn(f"zone '{z}' assigned to {owner_id} is not in VALENCIA_ZONES — skipped")
                continue
            owner_by_zone[z] = (owner_id, color, armies)
    return owner_by_zone


def _seed_users(db, players: list[dict], pwd) -> None:
    """Crea documentos `users/{id}` con hash bcrypt y todos los campos extendidos."""
    from google.cloud import firestore
    for p in players:
        db.collection("users").document(p["id"]).set({
            "id": p["id"],
            "name": p["name"],
            "email": p["email"],
            "hashed_password": pwd.hash(p["password"]),
            "clan_id": None,
            "steps_total": p["total_steps"],
            "power_points": p["power_points"],
            "gold": p["gold"],
            "level": p["level"],
            "clan_color": p["clan_color"],
            "spawn_zone": p["spawn_zone"],
            "starting_armies": p["armies"],
            "battles_won": p["battles_won"],
            "battles_lost": p["battles_lost"],
            "kills": p["kills"],
            "created_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    ok(f"{len(players)} users/ written (login: {players[0]['email']} / demo1234)")


def _seed_zones(db, zones: list[dict], owner_by_zone: dict, started_at: str) -> None:
    """Persiste `zones/{id}` con su geometría estática + estado (owner, armies, defensa)."""
    conquered = 0
    for z in zones:
        owner_tuple = owner_by_zone.get(z["id"])
        doc = dict(z)
        if owner_tuple:
            owner_id, color, armies = owner_tuple
            doc.update({
                "owner_clan_id": owner_id,
                "owner_color": color,
                "defense_level": armies,
                "conquered_at": started_at,
            })
            conquered += 1
        else:
            doc.update({
                "owner_clan_id": None,
                "owner_color": None,
                "defense_level": 0,
                "conquered_at": None,
            })
        db.collection("zones").document(z["id"]).set(doc, merge=True)
    ok(f"{len(zones)} zones/ written ({conquered} owned, {len(zones) - conquered} free)")


def _seed_balances(db, players: list[dict], zones: list[dict],
                   owner_by_zone: dict, now: datetime) -> None:
    """Crea las dos colecciones del contrato del equipo:
    `user_balance/` (por jugador) y `location_balance/` (por zona)."""
    for p in players:
        db.collection("user_balance").document(p["id"]).set({
            "armies": p["armies"],
            "total_steps": p["total_steps"],
            "gold": p["gold"],
            "updated_at": now,
            "username": p["name"],
            "email": p["email"],
        }, merge=True)
    ok(f"{len(players)} user_balance/ written (team contract schema)")

    for z in zones:
        owner_tuple = owner_by_zone.get(z["id"])
        if owner_tuple:
            owner_id, _, armies = owner_tuple
            payload = {"armies": armies, "owner": owner_id}
        else:
            payload = {"armies": 0, "owner": None}
        payload.update({"location_name": z["name"], "updated_at": now})
        db.collection("location_balance").document(z["id"]).set(payload, merge=True)
    ok(f"{len(zones)} location_balance/ written")


def _seed_battles(db, recent_battles: list[dict]) -> None:
    """Inserta el histórico de batallas demo en la colección `battles/`."""
    for i, b in enumerate(recent_battles):
        battle_id = f"battle-{b['ts'].replace(':', '').replace('-', '').replace('T', '')[:15]}-{i}"
        db.collection("battles").document(battle_id).set({
            **b,
            "ts": datetime.fromisoformat(b["ts"].replace("Z", "+00:00")),
        }, merge=True)
    ok(f"{len(recent_battles)} battles/ written (últimas batallas visibles en el dashboard)")


def seed_firestore(project: str, state: dict, zones: list[dict], dry_run: bool) -> None:
    """Orquestador: construye el mapa de propietarios y delega en los 4
    seed-helpers (users, zones, balances, battles). En modo dry-run sólo
    cuenta lo que escribiría."""
    section("Firestore — jugadores, zonas, balances y batallas")

    players = state["players"]
    recent_battles = state["recent_battles"]
    owner_by_zone = _build_owner_map(state["zone_ownership"], zones)

    if dry_run:
        info(f"would write users/ × {len(players)}")
        info(f"would write zones/ × {len(zones)}")
        info(f"would write user_balance/ × {len(players)} (with ongoing game stats)")
        info(f"would write location_balance/ × {len(zones)} ({len(owner_by_zone)} owned, {len(zones) - len(owner_by_zone)} free)")
        info(f"would write battles/ × {len(recent_battles)}")
        return

    try:
        from google.cloud import firestore
    except ImportError:
        sys.exit("[demo] google-cloud-firestore not installed. Run: pip install google-cloud-firestore passlib[bcrypt]")
    try:
        import bcrypt as _bcrypt
    except ImportError:
        sys.exit("[demo] bcrypt not installed. Run: pip install bcrypt")

    class _BcryptWrapper:
        def hash(self, password: str) -> str:
            return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    pwd = _BcryptWrapper()
    db = firestore.Client(project=project)
    now = datetime.now(timezone.utc)

    _seed_users(db, players, pwd)
    _seed_zones(db, zones, owner_by_zone, state["game_time"]["started_at"])
    _seed_balances(db, players, zones, owner_by_zone, now)
    _seed_battles(db, recent_battles)


# ---------------------------------------------------------------------------
# Publica unos mensajes de ejemplo a Pub/Sub para que Dataflow alimente BigQuery
# ---------------------------------------------------------------------------
def seed_pubsub(project: str, state: dict, dry_run: bool) -> None:
    section("Pub/Sub — mensajes de ejemplo para que la pipeline escriba en BigQuery")

    samples = state["environmental_factors"]["samples"]

    if dry_run:
        for s in samples:
            info(f"would publish to {s['source']}: {json.dumps(s)[:80]}")
        return

    try:
        from google.cloud import pubsub_v1
    except ImportError:
        warn("google-cloud-pubsub not installed — skipping Pub/Sub seed")
        warn("install with: pip install google-cloud-pubsub")
        return

    publisher = pubsub_v1.PublisherClient()
    published = 0
    for s in samples:
        topic_name = "air-quality" if s["source"] == "air_quality" else "weather"
        topic_path = publisher.topic_path(project, topic_name)
        try:
            future = publisher.publish(topic_path, json.dumps(s).encode("utf-8"))
            future.result(timeout=10)
            published += 1
        except Exception as exc:
            warn(f"publish to {topic_name} failed: {exc}")
    ok(f"{published}/{len(samples)} messages published to Pub/Sub")


# ---------------------------------------------------------------------------
# Imprime un resumen listo-para-jugar
# ---------------------------------------------------------------------------
def print_recap(project: str, state: dict) -> None:
    section("Demo lista — esto es lo que tienes ahora mismo")
    print()
    print(f"  {BOLD}Proyecto:{RESET} {project}")
    print(f"  {BOLD}Turno actual:{RESET} {state['game_time']['current_turn']}")
    print()
    print(f"  {BOLD}Jugadores demo (todos con pass {GREEN}demo1234{RESET}):{RESET}")
    for p in state["players"]:
        n_zones = len(state["zone_ownership"][p["id"]]["zones"])
        print(f"    • {p['email']:32s} {p['armies']:4d} armies · {n_zones:2d} zonas · {p['gold']:4d} gold · lvl {p['level']}")
    print()
    print(f"  {BOLD}Enlaces para mirar en la consola de GCP:{RESET}")
    print(f"    {DIM}Firestore:{RESET}  https://console.cloud.google.com/firestore/databases/-default-/data/panel?project={project}")
    print(f"    {DIM}Pub/Sub:{RESET}    https://console.cloud.google.com/cloudpubsub/topic/list?project={project}")
    print(f"    {DIM}BigQuery:{RESET}   https://console.cloud.google.com/bigquery?project={project}")
    print(f"    {DIM}Cloud Run:{RESET}  https://console.cloud.google.com/run?project={project}")
    print()
    print(f"  {BOLD}Siguiente paso:{RESET}")
    print(f"    1. Abre el frontend (Cloud Run → cloudrisk-web → URL pública)")
    print(f"    2. Login como norte@cloudrisk.app / demo1234")
    print(f"    3. Deberías ver el mapa con 38 zonas coloreadas (10 tuyas rosa Norte)")
    print(f"    4. Desde otra máquina / ventana incógnito: login como este@cloudrisk.app")
    print(f"       (ese es el líder con 12 zonas y 340 armies)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", default=os.environ.get("PROJECT_ID"),
                        help="GCP project ID (falls back to $PROJECT_ID)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written, don't touch anything")
    parser.add_argument("--no-pubsub", action="store_true",
                        help="Skip publishing sample messages to Pub/Sub")
    parser.add_argument("--no-firestore", action="store_true",
                        help="Skip Firestore writes (only Pub/Sub)")
    args = parser.parse_args()

    if not args.project:
        sys.exit("[demo] --project is required (or set PROJECT_ID env var)")

    fs_target = os.environ.get("FIRESTORE_EMULATOR_HOST")
    ps_target = os.environ.get("PUBSUB_EMULATOR_HOST")

    print(f"{BOLD}CloudRISK sembrar_demo{RESET}")
    print(f"  project: {args.project}")
    print(f"  firestore: {'emulator ' + fs_target if fs_target else 'REAL Firestore'}")
    print(f"  pub/sub:   {'emulator ' + ps_target if ps_target else 'REAL Pub/Sub'}")
    print(f"  dry-run:   {args.dry_run}")

    state = load_demo_state()
    zones = load_zones()

    if not args.no_firestore:
        seed_firestore(args.project, state, zones, args.dry_run)
    if not args.no_pubsub:
        seed_pubsub(args.project, state, args.dry_run)

    print_recap(args.project, state)


if __name__ == "__main__":
    main()
