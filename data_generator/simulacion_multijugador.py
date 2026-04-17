#!/usr/bin/env python3
"""
CloudRISK — Run N full Risk matches back-to-back and report aggregate stats.

Each simulation:
  1. POST /turn/setup  (distribute 86 zones 22/22/21/21, 2 armies each)
  2. Run up to MAX_MOVES of bot actions (random place/attack/end_turn)
  3. Record the winner (player with most zones at stop)
  4. Stop early when any player owns >= WIN_THRESHOLD zones

After N simulations: aggregate win counts, average moves, average conquest
ratio per player, and print a clean leaderboard.

Usage:
    python data_generator/simulacion_multijugador.py --runs 10
    python data_generator/simulacion_multijugador.py --runs 5 --threshold 40 --max-moves 300
"""
from __future__ import annotations

import argparse
import random
import time
from collections import Counter, defaultdict

import requests

API = "http://127.0.0.1:8080"
PASSWORD = "demo1234"
PLAYERS = [
    "norte@cloudrisk.app", "sur@cloudrisk.app",
    "este@cloudrisk.app", "oeste@cloudrisk.app",
]
NAMES = {
    "demo-player-001": "Norte", "demo-player-002": "Sur",
    "demo-player-003": "Este",  "demo-player-004": "Oeste",
}
COLORS = {"Norte": "\033[95m", "Sur": "\033[92m", "Este": "\033[96m", "Oeste": "\033[94m"}
RESET = "\033[0m"


def post(path, token=None, **json_body):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{API}{path}", headers=headers, json=json_body or None, timeout=8)


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{API}{path}", headers=headers, timeout=8).json()


def login_all() -> dict:
    tokens = {}
    for email in PLAYERS:
        r = requests.post(
            f"{API}/api/v1/users/login",
            data={"username": email, "password": PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=8,
        )
        r.raise_for_status()
        body = r.json()
        tokens[body["user"]["id"]] = {"token": body["access_token"]}
    return tokens


def bootstrap_power(tokens: dict) -> None:
    """Give every bot enough power to play the whole match."""
    for info in tokens.values():
        post("/api/v1/steps/sync", info["token"], steps=100_000)


def standings() -> tuple[Counter, list]:
    zones = get("/api/v1/zones/")
    owners = Counter(z.get("owner_clan_id") for z in zones if z.get("owner_clan_id"))
    return owners, zones


def act(player_id: str, tok: str, zones: list, adj: dict, rng: random.Random) -> tuple[str, bool]:
    """
    Una acción atómica del bot. Respeta reglas Risk v3:
      - Sólo puede atacar zonas ADYACENTES a una zona propia con >=2 armies.
      - Puede reclamar zonas libres adyacentes (más barato que atacar).
      - Si no puede atacar, refuerza la zona más débil.
    Devuelve (kind, succeeded).
    """
    owned = [z for z in zones if z.get("owner_clan_id") == player_id]
    free  = [z for z in zones if not z.get("owner_clan_id")]
    enemy = [z for z in zones if z.get("owner_clan_id") and z.get("owner_clan_id") != player_id]
    owned_ids = {z["id"] for z in owned}

    # 1. Si tenemos zonas libres adyacentes y >=3 armies de sobra, reclamarlas
    # es mucho más barato (no combate). Hazlo con 25% prob.
    if rng.random() < 0.25 and free and owned:
        for o in owned:
            if int(o.get("defense_level") or 0) < 3:
                continue
            neighbors = adj.get(o["id"], [])
            free_neighbors = [z for z in free if z["id"] in neighbors]
            if free_neighbors:
                target = rng.choice(free_neighbors)
                r = post(f"/api/v1/zones/{target['id']}/attack", tok,
                         from_zone_id=o["id"], attacker_dice=1)
                return "conquer", r.status_code == 200

    roll = rng.random()

    # 2. Refuerzo (40%): zona propia más débil
    if roll < 0.4 and owned:
        weakest = min(owned, key=lambda z: int(z.get("defense_level") or 0))
        amount = rng.randint(1, 3)
        r = post("/api/v1/actions/place", tok, location_id=weakest["id"], armies=amount)
        return "reinforce", r.status_code == 200

    # 3. Ataque: sólo contra enemigos ADYACENTES a alguna zona propia >=2 armies
    if owned and enemy:
        # Lista de pares (source, target) viables
        viable = []
        for o in owned:
            if int(o.get("defense_level") or 0) < 2:
                continue
            neighbors = set(adj.get(o["id"], []))
            for t in enemy:
                if t["id"] in neighbors:
                    viable.append((o, t))
        if viable:
            # Heurística: atacar el target más débil desde el source más fuerte
            # que lo tenga como vecino.
            viable.sort(key=lambda p: (
                int(p[1].get("defense_level") or 0),       # target débil primero
                -int(p[0].get("defense_level") or 0),      # source fuerte primero
            ))
            source, target = viable[0]
            dice = min(3, int(source.get("defense_level") or 2) - 1)
            if dice >= 1:
                r = post(f"/api/v1/zones/{target['id']}/attack", tok,
                         from_zone_id=source["id"], attacker_dice=dice)
                return "attack", r.status_code == 200

    return "skip", False


def run_one_match(sim_num: int, max_moves: int, win_threshold: int, verbose: bool, rng: random.Random) -> dict:
    """Run a single match. Returns {winner, moves, owners, duration_s}."""
    t0 = time.time()

    # Setup (distribute zones)
    any_token = next(iter(login_all().values()))["token"]
    r = post("/api/v1/turn/setup", any_token)
    r.raise_for_status()
    setup = r.json()
    if verbose:
        print(f"[sim {sim_num}] setup: {setup['zones_per_player']}")

    # Give each bot lots of power
    tokens = login_all()
    bootstrap_power(tokens)

    # Cargar grafo de adyacencia una sola vez (reglas Risk v3: sólo atacas
    # zonas vecinas). Formato: {zone_id: [neighbor_ids]}.
    adj_resp = get("/api/v1/zones/adjacency")
    adj = adj_resp.get("adjacency", {}) if isinstance(adj_resp, dict) else {}
    if verbose:
        print(f"[sim {sim_num}] adjacency: {len(adj)} zones loaded")

    # Run moves until someone wins or we hit the cap
    move = 0
    player_order = list(tokens.keys())
    stats = defaultdict(lambda: {"attacks": 0, "reinforces": 0, "conquests": 0, "conquers": 0})

    while move < max_moves:
        for pid in player_order:
            zones = get("/api/v1/zones/")
            owners = Counter(z.get("owner_clan_id") for z in zones if z.get("owner_clan_id"))

            # Early stop
            if owners.most_common(1) and owners.most_common(1)[0][1] >= win_threshold:
                break

            kind, ok = act(pid, tokens[pid]["token"], zones, adj, rng)
            if ok:
                stats[pid][f"{kind}s"] += 1
                move += 1
            # end turn to rotate
            post("/api/v1/turn/end", tokens[pid]["token"])

        else:
            continue
        break

    owners, _ = standings()
    winner_id = owners.most_common(1)[0][0] if owners else None

    return {
        "sim": sim_num,
        "winner": winner_id,
        "winner_name": NAMES.get(winner_id, "?"),
        "moves": move,
        "owners": dict(owners),
        "duration_s": round(time.time() - t0, 1),
        "stats": dict(stats),
    }


def print_leaderboard(owners: dict) -> None:
    total = sum(owners.values())
    print(f"  Resultado final ({total}/86 zonas):")
    for pid, count in sorted(owners.items(), key=lambda x: -x[1]):
        name = NAMES.get(pid, pid[:10])
        c = COLORS.get(name, "")
        bar = "█" * min(count, 40)
        print(f"    {c}{name:6s}{RESET} {count:3d}  {bar}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of simulations to run (default: 5)")
    parser.add_argument("--max-moves", type=int, default=200,
                        help="Max moves per match (default: 200)")
    parser.add_argument("--threshold", type=int, default=40,
                        help="Zones owned to declare a winner early (default: 40)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed (omit for variable runs)")
    parser.add_argument("--quiet", action="store_true",
                        help="Less verbose output")
    args = parser.parse_args()

    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    print("═" * 70)
    print(f" CloudRISK · corriendo {args.runs} simulaciones")
    print(f" max-moves={args.max_moves} · threshold={args.threshold} · seed={args.seed}")
    print("═" * 70)

    results = []
    for i in range(1, args.runs + 1):
        print(f"\n[SIM {i}/{args.runs}] iniciando...")
        res = run_one_match(i, args.max_moves, args.threshold, not args.quiet, rng)
        results.append(res)
        name = COLORS.get(res['winner_name'], '') + res['winner_name'] + RESET
        print(f"  Ganador: {name} · {res['moves']} movimientos · {res['duration_s']}s")
        print_leaderboard(res["owners"])

    # Aggregate
    print("\n" + "═" * 70)
    print(" AGREGADO")
    print("═" * 70)
    wins = Counter(r["winner_name"] for r in results)
    avg_moves = sum(r["moves"] for r in results) / len(results)
    avg_time = sum(r["duration_s"] for r in results) / len(results)

    print(f"\n Total simulaciones: {len(results)}")
    print(f" Moves/partida (media): {avg_moves:.1f}")
    print(f" Duración/partida (media): {avg_time:.1f} s")
    print()
    print(" Ranking de victorias:")
    for name in ["Norte", "Sur", "Este", "Oeste"]:
        c = wins[name]
        pct = c / len(results) * 100
        bar = "█" * int(pct / 4)
        cc = COLORS.get(name, "")
        print(f"   {cc}{name:6s}{RESET} {c:2d} victorias ({pct:5.1f}%)  {bar}")

    # Avg zones per player across all sims
    total_zones: dict = defaultdict(int)
    for r in results:
        for pid, count in r["owners"].items():
            total_zones[pid] += count
    print("\n Media de zonas por jugador al final:")
    for pid in ["demo-player-001", "demo-player-002", "demo-player-003", "demo-player-004"]:
        name = NAMES[pid]
        avg = total_zones[pid] / len(results)
        cc = COLORS.get(name, "")
        print(f"   {cc}{name:6s}{RESET} {avg:5.1f} zonas")

    print()


if __name__ == "__main__":
    main()
