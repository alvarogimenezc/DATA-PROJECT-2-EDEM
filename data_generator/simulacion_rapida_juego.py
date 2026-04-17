#!/usr/bin/env python3
"""
CloudRISK — FAST 4-bot match for demos.

Unlike bot_ia_riesgo.py which runs one thread per bot and paces by sleep,
this script walks the game sequentially as fast as the API allows. Useful
for recording a short preview clip: you'll see ~1 move per ~100 ms.

Same heuristic as the long-running bot, but turns advance on every move
and the loop stops once a player owns >= WIN_THRESHOLD zones or we hit
MAX_MOVES.
"""
from __future__ import annotations

import random
import time
from collections import Counter

import requests

API = "http://127.0.0.1:8080"
PASSWORD = "demo1234"
PLAYERS = [
    "norte@cloudrisk.app", "sur@cloudrisk.app",
    "este@cloudrisk.app", "oeste@cloudrisk.app",
]
NAMES = {
    "demo-player-001": "Norte",  "demo-player-002": "Sur",
    "demo-player-003": "Este",   "demo-player-004": "Oeste",
}

WIN_THRESHOLD = 30   # first player to own >=30 zones wins the demo
MAX_MOVES     = 400  # safety cap

rng = random.Random(1234)


def post(path, token, **json):
    return requests.post(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, json=json or None, timeout=5)


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{API}{path}", headers=headers, timeout=5).json()


def login_all():
    tokens = {}
    for email in PLAYERS:
        r = requests.post(
            f"{API}/api/v1/users/login",
            data={"username": email, "password": PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        r.raise_for_status()
        body = r.json()
        tokens[body["user"]["id"]] = {
            "token": body["access_token"],
            "email": email,
            "name": body["user"]["name"],
        }
    return tokens


def bootstrap_power(tokens):
    for info in tokens.values():
        post("/api/v1/steps/sync", info["token"], steps=10000)


def standings():
    zones = get("/api/v1/zones/")
    owners = Counter(z.get("owner_clan_id") for z in zones if z.get("owner_clan_id"))
    return owners, zones


def print_standings(moves, owners):
    total = sum(owners.values())
    print(f"\n─── move {moves} │ total {total}/87 ───")
    for k, v in owners.most_common():
        bar = "#" * min(v, 40)
        print(f"  {NAMES.get(k, k[:10]):6s} {v:3d}  {bar}")


def act(player_id, info, zones):
    """One atomic action: place or attack, then end the turn."""
    tok = info["token"]
    me_power = int(get("/api/v1/users/me", tok).get("power_points") or 0)
    owned = [z for z in zones if z.get("owner_clan_id") == player_id]
    free  = [z for z in zones if not z.get("owner_clan_id")]
    enemy = [z for z in zones if z.get("owner_clan_id") and z.get("owner_clan_id") != player_id]

    if me_power <= 0 and not owned:
        return False

    roll = rng.random()

    if free and (roll < 0.4 or not owned):
        target = rng.choice(free)
        amount = max(1, min(me_power, rng.randint(2, 6)))
        post("/api/v1/armies/place", tok, location_id=target["id"], amount=amount)
        return True

    if roll < 0.75 and owned and enemy:
        attackers = [z for z in owned if int(z.get("defense_level") or 0) >= 2]
        if attackers:
            source = max(attackers, key=lambda z: int(z.get("defense_level") or 0))
            target = min(enemy, key=lambda z: int(z.get("defense_level") or 0))
            dice = min(3, int(source.get("defense_level") or 2) - 1)
            if dice >= 1:
                r = post(f"/api/v1/zones/{target['id']}/attack", tok,
                         from_zone_id=source["id"], attacker_dice=dice)
                if r.status_code == 200:
                    j = r.json()
                    arrow = "[CONQ]" if j.get("conquered") else "[def.]"
                    print(f"  {NAMES[player_id]:6s} {arrow} {source['id']:22s} → {target['id']:22s} "
                          f"{j.get('attacker_rolls')} vs {j.get('defender_rolls')}"
                          f"  (−{j.get('attacker_losses')} / −{j.get('defender_losses')})")
                    return True

    # reinforce weakest
    if owned and me_power > 0:
        w = min(owned, key=lambda z: int(z.get("defense_level") or 0))
        post("/api/v1/armies/place", tok, location_id=w["id"], amount=min(me_power, 3))
        return True

    return False


def main():
    print("=== FAST 4-bot CloudRISK sim ===")
    tokens = login_all()
    print(f"logged in: {', '.join(NAMES[k] for k in tokens)}")
    bootstrap_power(tokens)
    print("bootstrap: +10000 steps each (~100 power_points)\n")

    for move in range(1, MAX_MOVES + 1):
        turn = get("/api/v1/turn/")
        pid = turn["current_player_id"]
        if pid not in tokens:
            break
        _, zones = standings()
        act(pid, tokens[pid], zones)
        # end the turn to rotate
        post("/api/v1/turn/end", tokens[pid]["token"])

        if move % 20 == 0:
            owners, _ = standings()
            print_standings(move, owners)

        owners, _ = standings()
        if owners and owners.most_common(1)[0][1] >= WIN_THRESHOLD:
            winner, count = owners.most_common(1)[0]
            print(f"\n================================")
            print(f"  WINNER: {NAMES[winner]} with {count} zones")
            print(f"================================")
            print_standings(move, owners)
            return

        time.sleep(0.08)   # tiny pause so the frontend can catch up

    print("\nMax moves reached, game stalled. Final state:")
    owners, _ = standings()
    print_standings(MAX_MOVES, owners)


if __name__ == "__main__":
    main()
