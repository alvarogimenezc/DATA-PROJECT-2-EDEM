#!/usr/bin/env python3
"""
Script para poblar Firestore con datos básicos de prueba.

Lee de:
  - data/players.json (usuarios)
  - backend/cloudrisk_api/database/almacen_en_memoria.py (zonas de Valencia)

Uso:
    # Subir al proyecto real
    python scripts/sembrar_firestore.py --project cloudrisk-492619

    # Ver qué haría sin subir nada (Simulación)
    python scripts/sembrar_firestore.py --project cloudrisk-492619 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"


def load_players() -> list[dict]:
    if not PLAYERS_JSON.exists():
        sys.exit(f"[seed] players file not found: {PLAYERS_JSON}")
    with PLAYERS_JSON.open(encoding="utf-8") as f:
        return json.load(f).get("players", [])


def load_zones() -> list[dict]:
    """Import VALENCIA_ZONES from the backend module without booting the API."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from cloudrisk_api.database.almacen_en_memoria import VALENCIA_ZONES  # type: ignore
    return list(VALENCIA_ZONES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=os.environ.get("PROJECT_ID"),
                        help="GCP project ID. Falls back to $PROJECT_ID.")
    parser.add_argument("--users-collection", default="users")
    parser.add_argument("--zones-collection", default="zones")
    parser.add_argument("--user-balance-collection", default="user_balance",
                        help="Team-schema collection for per-player armies. Written when --team-schema is set.")
    parser.add_argument("--location-balance-collection", default="location_balance",
                        help="Team-schema collection for per-zone armies/owner. Written when --team-schema is set.")
    parser.add_argument("--team-schema", action="store_true",
                        help="ALSO write the two collections the team's CloudRISK pipeline reads: "
                             "user_balance/{player_id} and location_balance/{location_id}. "
                             "Our own users/zones collections are still written; this is dual-write.")
    parser.add_argument("--starting-armies-from", choices=["json", "fixed"], default="json",
                        help="Where to read the initial 'armies' value for user_balance: "
                             "'json' uses data/players.json::starting_armies, 'fixed' uses --fixed-armies.")
    parser.add_argument("--fixed-armies", type=int, default=10,
                        help="Initial armies per player when --starting-armies-from=fixed.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written, don't touch Firestore.")
    parser.add_argument("--skip-passwords", action="store_true",
                        help="Don't include hashed_password in user docs (useful when the team backend manages auth elsewhere).")
    args = parser.parse_args()

    if not args.project:
        sys.exit("[seed] --project is required (or set PROJECT_ID env var)")

    emulator = os.environ.get("FIRESTORE_EMULATOR_HOST")
    target = f"emulator {emulator}" if emulator else f"REAL Firestore project {args.project}"
    print(f"[seed] Target: {target}")
    print(f"[seed] Dry run: {args.dry_run}")

    players = load_players()
    zones = load_zones()
    print(f"[seed] {len(players)} players, {len(zones)} zones to write.")

    def _starting_armies(p: dict) -> int:
        return p.get("starting_armies", 0) if args.starting_armies_from == "json" else args.fixed_armies

    if args.dry_run:
        print(f"\n--- {args.users_collection}/ (our schema) ---")
        for p in players:
            print(f"  {p['id']:<20} email={p['email']:<30} clan_color={p.get('clan_color')}")
        print(f"\n--- {args.zones_collection}/ (our schema) ---")
        for z in zones[:3]:
            print(f"  {z['id']:<25} name={z['name']}")
        print(f"  ...and {len(zones) - 3} more zones")
        if args.team_schema:
            print(f"\n--- {args.user_balance_collection}/ (TEAM schema, dual-write) ---")
            for p in players:
                print(f"  {p['id']:<20} {{ armies: {_starting_armies(p)}, total_steps: 0, updated_at: <now> }}")
            print(f"\n--- {args.location_balance_collection}/ (TEAM schema, dual-write) ---")
            for z in zones[:3]:
                print(f"  {z['id']:<25} {{ armies: 0, owner: null, updated_at: <now> }}")
            print(f"  ...and {len(zones) - 3} more zone-balance docs")
        return

    
    try:
        from google.cloud import firestore
    except ImportError:
        sys.exit("[seed] google-cloud-firestore not installed. Run: pip install -r backend/requirements.txt")

    try:
        from passlib.context import CryptContext
    except ImportError:
        sys.exit("[seed] passlib not installed. Run: pip install -r backend/requirements.txt")

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    db = firestore.Client(project=args.project)

    for p in players:
        user_id = p.get("id") or str(uuid.uuid4())
        doc = {
            "id": user_id,
            "name": p["name"],
            "email": p["email"],
            "clan_id": None,
            "steps_total": 0,
            "power_points": 0,
            "gold": p.get("starting_gold", 0),
            "level": 1,
            "created_at": firestore.SERVER_TIMESTAMP,
            "clan_color": p.get("clan_color"),
            "spawn_zone": p.get("spawn_zone"),
            "starting_armies": p.get("starting_armies", 0),
        }
        if not args.skip_passwords:
            doc["hashed_password"] = pwd.hash(p["password"])
        db.collection(args.users_collection).document(user_id).set(doc, merge=True)
        print(f"  ok user/{user_id} ({p['email']})")

    for z in zones:
        db.collection(args.zones_collection).document(z["id"]).set(z, merge=True)
    print(f"  ok {len(zones)} zones written to {args.zones_collection}/")

    if args.team_schema:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        
        for p in players:
            user_id = p.get("id") or str(uuid.uuid4())
            db.collection(args.user_balance_collection).document(user_id).set({
                "armies": _starting_armies(p),
                "total_steps": 0,
                "updated_at": now,
                "username": p["name"],
                "email": p["email"],
            }, merge=True)
        print(f"  ok {len(players)} player balances written to {args.user_balance_collection}/ (team schema)")

        
        for z in zones:
            db.collection(args.location_balance_collection).document(z["id"]).set({
                "armies": 0,
                "owner": None,
                "updated_at": now,
                "location_name": z["name"],
            }, merge=True)
        print(f"  ok {len(zones)} location balances written to {args.location_balance_collection}/ (team schema)")

    print(f"[seed] Done. Wrote {len(players)} users and {len(zones)} zones to {target}.")


if __name__ == "__main__":
    main()
