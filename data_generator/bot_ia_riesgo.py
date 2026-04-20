#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

DEFAULT_API = "http://localhost:8080"
DEFAULT_PASSWORD = "demo1234"
DEFAULT_BOTS = ["sur@cloudrisk.app", "este@cloudrisk.app", "oeste@cloudrisk.app"]

# Pesos de decisión para la IA. La función decide() los lee de arriba a abajo.
WEIGHT_EXPANSION  = 0.40   # place into an empty zone (if any are left)
WEIGHT_ATTACK     = 0.35   # attack the weakest adjacent enemy
WEIGHT_DEFENSE    = 0.20   # reinforce our own weakest zone
WEIGHT_RANDOM     = 0.05   # pad a random owned zone

RESERVE_POWER = 0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-12s %(levelname)s %(message)s")
log = logging.getLogger("bot")


@dataclass
class BotSession:
    email: str
    token: str
    user_id: str
    name: str


class RiskAIBot(threading.Thread):
    def __init__(self, api_base: str, email: str, password: str, interval_s: int, rng: random.Random):
        super().__init__(daemon=True)
        self.api_base = api_base.rstrip("/")
        self.email = email
        self.password = password
        self.interval_s = interval_s
        self.rng = rng
        self.session: Optional[BotSession] = None
        self.log = logging.getLogger(f"bot[{email.split('@')[0]}]")
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    # ---------- HTTP helpers ----------

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.session.token}"} if self.session else {}

    def login(self) -> None:
        resp = requests.post(
            f"{self.api_base}/api/v1/users/login",
            data={"username": self.email, "password": self.password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        resp.raise_for_status()
        body = resp.json()
        self.session = BotSession(
            email=self.email,
            token=body["access_token"],
            user_id=body["user"]["id"],
            name=body["user"]["name"],
        )
        self.log.info("logged in (user_id=%s)", self.session.user_id[:8])

       # Recarga inicial de pasos si el bot no tiene poder para jugar
        try:
            me = self._get("/api/v1/users/me")
            if int(me.get("power_points") or 0) < 20:
                self._post("/api/v1/steps/sync", {"steps": 10000})
                self.log.info("bootstrapped: +10000 steps")
        except requests.HTTPError as exc:
            self.log.warning("bootstrap failed: %s", exc)

    def _get(self, path: str):
        r = requests.get(f"{self.api_base}{path}", headers=self._auth_headers(), timeout=5)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json_body: Optional[dict] = None):
        r = requests.post(f"{self.api_base}{path}", headers=self._auth_headers(),
                          json=json_body, timeout=5)
        r.raise_for_status()
        return r.json() if r.content else {}

# ---------- Estado del juego ----------
    def snapshot(self) -> dict:
        """Grab everything the bot needs in one pass."""
        zones = self._get("/api/v1/zones/")
        me = self._get("/api/v1/users/me")
        multipliers = self._get("/api/v1/multipliers/")
        return {"zones": zones, "me": me, "multipliers": multipliers}

# ---------- Lógica de Decisión ----------
    def decide(self, snap: dict) -> Optional[tuple[str, dict]]:
        
        me = snap["me"]
        zones = snap["zones"]
        my_id = me["id"]
        power = int(me.get("power_points") or 0)

        owned     = [z for z in zones if z.get("owner_clan_id") == my_id]
        free      = [z for z in zones if not z.get("owner_clan_id")]
        enemy     = [z for z in zones if z.get("owner_clan_id") and z.get("owner_clan_id") != my_id]

        # 1. Primera conquista si no tenemos zonas
        if not owned and free and power >= 1:
            target = self.rng.choice(free)
            return ("place", {"location_id": target["id"], "amount": max(1, min(power, 5))})

        # 2. Selección de acción basada en heurística
        if power > RESERVE_POWER:
            roll = self.rng.random()
            thresh = 0.0

            thresh += WEIGHT_EXPANSION
            if roll < thresh and free:
                # Expand: claim any free zone (adjacency not modelled yet; pick random).
                target = self.rng.choice(free)
                amount = max(1, min(power, self.rng.randint(2, 6)))
                return ("place", {"location_id": target["id"], "amount": amount})

            thresh += WEIGHT_ATTACK
            if roll < thresh and owned and enemy:
                # Find a source zone with >=2 armies, pick the weakest enemy as target.
                attackers = [z for z in owned if int(z.get("defense_level") or 0) >= 2]
                if attackers:
                    source = max(attackers, key=lambda z: int(z.get("defense_level") or 0))
                    target = min(enemy, key=lambda z: int(z.get("defense_level") or 0))
                    dice = min(3, int(source.get("defense_level") or 2) - 1)
                    if dice >= 1:
                        return ("attack", {
                            "target_id": target["id"],
                            "from_zone_id": source["id"],
                            "attacker_dice": dice,
                        })

            thresh += WEIGHT_DEFENSE
            if roll < thresh and owned:
                # Reinforce the weakest own zone.
                weakest = min(owned, key=lambda z: int(z.get("defense_level") or 0))
                amount = max(1, min(power, self.rng.randint(3, 8)))
                return ("place", {"location_id": weakest["id"], "amount": amount})

            # Fallback: random owned zone.
            if owned:
                target = self.rng.choice(owned)
                return ("place", {"location_id": target["id"], "amount": max(1, min(power, 2))})

            # Only enemeeey zones exist + no usable owned → try attacking anyway
            if enemy and not owned and free:
                target = self.rng.choice(free)
                return ("place", {"location_id": target["id"], "amount": max(1, min(power, 3))})

        # 3) No power and nothing interesting → idle this tick.
        return None

    # ---------- Main loop ----------

    def step(self) -> None:
        try:
            # Turn gate: only act when it's our turn, and relinquish when done.
            try:
                turn = self._get("/api/v1/turn/")
                if turn.get("current_player_id") != self.session.user_id:
                    return   # not our turn — silent wait
            except Exception:
                turn = None   # /turn/ not deployed → fall through to legacy free-for-all

            snap = self.snapshot()
            action = self.decide(snap)
            if action is None:
                # Nothing useful to do AND it's our turn → end turn so the next
                # player can play. Without this the whole game dead-locks on a
                # bot that ran out of power.
                if turn:
                    try:
                        self._post("/api/v1/turn/end")
                        self.log.info("out of moves → end turn")
                    except Exception as exc:
                        # Mejor saberlo: si /turn/end falla repetidamente la
                        # rotación se atasca. Sólo logueamos para no romper.
                        self.log.warning("end-turn after no-op failed: %s", exc)
                return
            verb, params = action
            if verb == "place":
                resp = self._post("/api/v1/armies/place", params)
                base = resp.get("base_amount")
                eff  = resp.get("effective_amount")
                mult = resp.get("multiplier")
                self.log.info(
                    "place %s on %s → defense=%s (base=%s, x%s → eff=%s)",
                    params["amount"], params["location_id"],
                    resp.get("new_defense"), base, mult, eff,
                )
            elif verb == "attack":
                target = params.pop("target_id")
                resp = self._post(f"/api/v1/zones/{target}/attack", params)
                if resp.get("conquered"):
                    self.log.info(
                        "ATTACK %s → %s [CONQ!] %s vs %s (lost %s, enemy lost %s)",
                        params["from_zone_id"], target,
                        resp.get("attacker_rolls"), resp.get("defender_rolls"),
                        resp.get("attacker_losses"), resp.get("defender_losses"),
                    )
                else:
                    self.log.info(
                        "attack %s → %s  %s vs %s (lost %s, enemy lost %s)",
                        params["from_zone_id"], target,
                        resp.get("attacker_rolls"), resp.get("defender_rolls"),
                        resp.get("attacker_losses"), resp.get("defender_losses"),
                    )
            # After any successful action, end the turn so rotation is steady.
            # One action per turn keeps the rhythm visible in the preview.
            try:
                self._post("/api/v1/turn/end")
            except Exception as exc:
                self.log.warning("end-turn after action failed: %s", exc)
        except requests.HTTPError as exc:
            # Not catastrophic — typically "no power" or "zone not found" when
            # the game state changed between snapshot and action.
            self.log.warning("step failed: %s %s", exc, getattr(exc.response, "text", "")[:120])
        except Exception as exc:  # noqa: BLE001
            self.log.warning("step crashed: %s", exc)

    def run(self) -> None:
        try:
            self.login()
        except Exception as exc:
            self.log.error("login failed: %s", exc)
            return
        # Small jitter so 3 bots don't all hit the API at the exact same second.
        time.sleep(self.rng.uniform(0, self.interval_s / 2))
        while not self._stop.is_set():
            self.step()
            self._stop.wait(self.interval_s)
        self.log.info("stopped")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default=DEFAULT_API, help="API base URL.")
    p.add_argument("--players", nargs="+", default=DEFAULT_BOTS,
                   help="Emails of the accounts the bots should log in as.")
    p.add_argument("--password", default=DEFAULT_PASSWORD, help="Shared password for seeded players.")
    p.add_argument("--interval", type=int, default=10, help="Seconds between decisions per bot.")
    p.add_argument("--seed", type=int, default=None, help="Seed the RNG for reproducibility.")
    return p.parse_args()


def main():
    args = _parse_args()
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    bots = [RiskAIBot(args.api, email, args.password, args.interval, rng)
            for email in args.players]

    print(f"\nStarting {len(bots)} Risk-AI bots against {args.api}")
    print(f"  interval: {args.interval}s  weights: expand={WEIGHT_EXPANSION} defend={WEIGHT_DEFENSE} rand={WEIGHT_RANDOM}")
    print(f"  players: {', '.join(args.players)}")
    print("  Ctrl+C to stop.\n")

    for b in bots:
        b.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bots...")
        for b in bots:
            b.stop()
        for b in bots:
            b.join(timeout=2)


if __name__ == "__main__":
    main()
