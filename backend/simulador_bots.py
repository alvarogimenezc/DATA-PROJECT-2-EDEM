"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              CloudRISK — BOT SIMULATION / STRESS TEST                     ║
║                                                                              ║
║  4 bots compete simultaneously in the real game engine (in-memory store).   ║
║  All interactions go through the actual FastAPI routers, using an            ║
║  httpx.AsyncClient with ASGITransport — no mocks, no shortcuts.              ║
║                                                                              ║
║  Run:  USE_LOCAL_STORE=1 python simulador_bots.py                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Bot strategies
──────────────
  CONQUISTADOR  — Greedy zone taker. Rushes free zones, then attacks weakly
                  defended enemy territory.
  INVASOR       — Pure aggressor. Targets zones owned by rival clans.
                  Picks the zone with the lowest defense_level.
  CORREDOR      — Runner first. Generates maximum power via step-sync before
                  any cloudrisk attempt, then steamrolls.
  DEFENSOR      — Fortifier. Conquers and holds a small number of key zones,
                  resolves battles that are initiated against it.

Stress-test scenarios (run after individual bot rounds)
────────────────────────────────────────────────────────
  S1 — All 4 bots race to conquer the same free zone simultaneously.
  S2 — Two bots attack the same enemy zone at the same time (only one should succeed).
  S3 — A bot that is NOT a battle participant tries to resolve that battle (403 expected).
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from datetime import datetime
from typing import Optional

# ── Force in-memory store before any import that checks the env var ──────────
os.environ.setdefault("USE_LOCAL_STORE", "1")

import httpx
from httpx import AsyncClient

# ── Now safe to import the app ───────────────────────────────────────────────
from cloudrisk_api.main import app   # noqa: E402  (import after env set)

# ══════════════════════════════════════════════════════════════════════════════
#  Logging helpers
# ══════════════════════════════════════════════════════════════════════════════

RESET  = "\033[0m"
BOLD   = "\033[1m"
COLORS = {
    "CONQUISTADOR": "\033[38;5;202m",   # orange
    "INVASOR":      "\033[38;5;196m",   # red
    "CORREDOR":     "\033[38;5;118m",   # lime
    "DEFENSOR":     "\033[38;5;39m",    # blue
    "SYSTEM":       "\033[38;5;245m",   # grey
    "STRESS":       "\033[38;5;220m",   # yellow
}

_log_lock = asyncio.Lock()


async def log(bot_name: str, msg: str, level: str = "info") -> None:
    prefix = {
        "info":    "   ",
        "ok":      "✅ ",
        "error":   "❌ ",
        "warn":    "⚠  ",
        "battle":  "⚔  ",
        "conquer": "🏴 ",
        "step":    "👟 ",
        "stress":  "💥 ",
    }.get(level, "   ")
    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
    color = COLORS.get(bot_name, COLORS["SYSTEM"])
    async with _log_lock:
        print(f"{COLORS['SYSTEM']}[{ts}]{RESET} {color}{BOLD}[{bot_name:12s}]{RESET} {prefix}{msg}")


# ══════════════════════════════════════════════════════════════════════════════
#  Combat log — structured event record
# ══════════════════════════════════════════════════════════════════════════════

_combat_log: list[dict] = []
_combat_log_lock = asyncio.Lock()


async def record(event_type: str, actor: str, detail: dict) -> None:
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "event": event_type,
        "actor": actor,
        **detail,
    }
    async with _combat_log_lock:
        _combat_log.append(entry)


# ══════════════════════════════════════════════════════════════════════════════
#  Bot base class
# ══════════════════════════════════════════════════════════════════════════════

class Bot:
    def __init__(
        self,
        name: str,
        clan_name: str,
        clan_color: str,
        email_suffix: str,
        client: AsyncClient,
    ):
        self.name = name
        self.clan_name = clan_name
        self.clan_color = clan_color
        self.email = f"bot_{email_suffix}@simulation-bots.com"
        self.password = "Simulation#1"
        self.client = client

        # filled after registration
        self.user_id: Optional[str] = None
        self.clan_id: Optional[str] = None
        self.token: Optional[str] = None

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, path: str, **kw) -> httpx.Response:
        return await self.client.get(path, headers=self._headers(), **kw)

    async def post(self, path: str, json: dict | None = None, **kw) -> httpx.Response:
        return await self.client.post(
            path, json=json or {}, headers=self._headers(), **kw
        )

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """Register user, create clan."""
        r = await self.client.post(
            "/api/v1/users/register",
            json={"name": self.name, "email": self.email, "password": self.password},
        )
        if r.status_code not in (200, 201):
            await log(self.name, f"Registration failed: {r.text}", "error")
            raise RuntimeError(f"{self.name} could not register")
        data = r.json()
        self.token = data["access_token"]
        self.user_id = data["user"]["id"]
        await log(self.name, f"Registered — user_id={self.user_id[:8]}…", "ok")

        r = await self.post(
            "/api/v1/clans/",
            json={"name": self.clan_name, "color": self.clan_color},
        )
        if r.status_code not in (200, 201):
            await log(self.name, f"Clan creation failed: {r.text}", "error")
            raise RuntimeError(f"{self.name} could not create clan {self.clan_name}")
        self.clan_id = r.json()["id"]
        await log(self.name, f"Clan '{self.clan_name}' created — clan_id={self.clan_id[:8]}…", "ok")

    # ── Game actions ──────────────────────────────────────────────────────────

    async def sync_steps(self, steps: int) -> dict | None:
        r = await self.post("/api/v1/steps/sync", json={"steps": steps})
        if r.status_code == 201:
            d = r.json()
            power = d.get("power_points_earned", d.get("power_earned", 0))
            gold  = d.get("gold_earned", 0)
            await log(self.name, f"Synced {steps:,} steps → +{power} power / +{gold} gold", "step")
            await record("step_sync", self.name, {"steps": steps, "power_earned": power})
            return d
        await log(self.name, f"Step sync failed ({r.status_code}): {r.text}", "warn")
        return None

    async def list_zones(self) -> list[dict]:
        r = await self.get("/api/v1/zones/")
        return r.json() if r.status_code == 200 else []

    async def conquer_zone(self, zone: dict) -> bool:
        r = await self.post(f"/api/v1/zones/{zone['id']}/conquer")
        if r.status_code == 200:
            await log(self.name, f"Conquered '{zone['name']}' (def={zone.get('defense_level',0)})", "conquer")
            await record("conquer", self.name, {
                "zone_id": zone["id"], "zone_name": zone["name"],
                "clan_id": self.clan_id,
            })
            return True
        err = r.json().get("detail", r.text)
        await log(self.name, f"Cannot conquer '{zone['name']}': {err}", "warn")
        return False

    async def initiate_battle(self, zone: dict) -> dict | None:
        r = await self.post("/api/v1/battles/", json={"zone_id": zone["id"]})
        if r.status_code == 201:
            battle = r.json()
            await log(
                self.name,
                f"Battle started on '{zone['name']}' — battle_id={battle['id'][:8]}…",
                "battle",
            )
            await record("battle_start", self.name, {
                "battle_id": battle["id"], "zone_id": zone["id"],
                "zone_name": zone["name"],
                "attacker_clan": self.clan_id,
                "defender_clan": zone.get("owner_clan_id"),
            })
            return battle
        err = r.json().get("detail", r.text)
        await log(self.name, f"Attack on '{zone['name']}' failed: {err}", "error")
        await record("battle_fail", self.name, {
            "zone_id": zone["id"], "zone_name": zone["name"], "reason": err,
        })
        return None

    async def resolve_battle(self, battle: dict) -> dict | None:
        r = await self.post(f"/api/v1/battles/{battle['id']}/resolve")
        if r.status_code == 200:
            d = r.json()
            emoji = "🏆" if d["result"] == "attacker_wins" else "🛡 "
            await log(
                self.name,
                f"Battle resolved: {d['result']} | "
                f"atk={d['attacker_roll']} vs def={d['defender_roll']}  {emoji}",
                "ok",
            )
            await record("battle_resolve", self.name, {
                "battle_id": battle["id"],
                "result": d["result"],
                "attacker_roll": d["attacker_roll"],
                "defender_roll": d["defender_roll"],
            })
            return d
        err = r.json().get("detail", r.text)
        await log(self.name, f"Resolve failed ({r.status_code}): {err}", "warn")
        await record("battle_resolve_fail", self.name, {
            "battle_id": battle["id"], "reason": err,
        })
        return None

    async def get_me(self) -> dict:
        r = await self.get("/api/v1/users/me")
        return r.json() if r.status_code == 200 else {}


# ══════════════════════════════════════════════════════════════════════════════
#  Individual bot strategies
# ══════════════════════════════════════════════════════════════════════════════

async def run_conquistador(bot: Bot, rounds: int = 4) -> None:
    """Greedy: take free zones, then attack weak enemy zones."""
    await log(bot.name, "Strategy: CONQUISTADOR — rush free zones, then attack weak ones")

    # Build power first
    await bot.sync_steps(500)

    for rnd in range(rounds):
        await log(bot.name, f"— Round {rnd + 1}/{rounds} —")
        zones = await bot.list_zones()
        random.shuffle(zones)

        # Priority 1: free zones
        free = [z for z in zones if not z.get("owner_clan_id")]
        if free:
            await bot.conquer_zone(free[0])
            await asyncio.sleep(0.1)

        # Priority 2: enemy zones with defense_level == 0
        enemy = [
            z for z in zones
            if z.get("owner_clan_id") and z["owner_clan_id"] != bot.clan_id
            and z.get("defense_level", 0) == 0
        ]
        if enemy:
            target = enemy[0]
            battle = await bot.initiate_battle(target)
            if battle:
                await asyncio.sleep(0.2)
                await bot.resolve_battle(battle)

        await asyncio.sleep(0.3)


async def run_invasor(bot: Bot, rounds: int = 4) -> None:
    """Pure aggressor: always attacks the weakest enemy zone."""
    await log(bot.name, "Strategy: INVASOR — pure aggression, target weakest defense")

    await bot.sync_steps(300)

    for rnd in range(rounds):
        await log(bot.name, f"— Round {rnd + 1}/{rounds} —")
        zones = await bot.list_zones()

        enemy = [
            z for z in zones
            if z.get("owner_clan_id") and z["owner_clan_id"] != bot.clan_id
        ]
        if not enemy:
            # No enemy zones yet — conquer a free one to have something
            free = [z for z in zones if not z.get("owner_clan_id")]
            if free:
                await bot.conquer_zone(random.choice(free))
        else:
            # Attack the easiest target
            target = min(enemy, key=lambda z: z.get("defense_level", 0))
            battle = await bot.initiate_battle(target)
            if battle:
                await asyncio.sleep(0.15)
                await bot.resolve_battle(battle)

        await asyncio.sleep(0.3)


async def run_corredor(bot: Bot, rounds: int = 4) -> None:
    """Runner: max steps → max power → conquer everything."""
    await log(bot.name, "Strategy: CORREDOR — generate massive power, then dominate")

    # Big step sync first
    for _ in range(3):
        steps = random.randint(2000, 5000)
        await bot.sync_steps(steps)
        await asyncio.sleep(0.05)

    for rnd in range(rounds):
        await log(bot.name, f"— Round {rnd + 1}/{rounds} —")
        zones = await bot.list_zones()
        random.shuffle(zones)

        # Take anything free
        for zone in zones:
            if not zone.get("owner_clan_id"):
                await bot.conquer_zone(zone)
                await asyncio.sleep(0.05)
                break

        # Also attack with power advantage
        me = await bot.get_me()
        my_power = me.get("power_points", 0)
        enemy = [
            z for z in zones
            if z.get("owner_clan_id") and z["owner_clan_id"] != bot.clan_id
        ]
        if enemy and my_power > 50:
            target = random.choice(enemy)
            battle = await bot.initiate_battle(target)
            if battle:
                await asyncio.sleep(0.2)
                await bot.resolve_battle(battle)

        await asyncio.sleep(0.3)


async def run_defensor(bot: Bot, rounds: int = 4) -> None:
    """Fortifier: conquer key zones, resolve incoming battles."""
    await log(bot.name, "Strategy: DEFENSOR — conquer and fortify key zones")

    await bot.sync_steps(400)

    for rnd in range(rounds):
        await log(bot.name, f"— Round {rnd + 1}/{rounds} —")
        zones = await bot.list_zones()

        # Conquer high-value free zones (value >= 6)
        premium_free = [
            z for z in zones
            if not z.get("owner_clan_id") and z.get("value", 0) >= 6
        ]
        if premium_free:
            await bot.conquer_zone(random.choice(premium_free))

        # Check for ongoing battles on own zones — resolve as defender
        r = await bot.get("/api/v1/battles/")
        if r.status_code == 200:
            ongoing = r.json()
            my_zones = {z["id"] for z in zones if z.get("owner_clan_id") == bot.clan_id}
            my_battles = [b for b in ongoing if b.get("zone_id") in my_zones]
            for battle in my_battles[:2]:
                await log(bot.name, f"Defending battle {battle['id'][:8]}… on zone {battle['zone_id']}")
                await bot.resolve_battle(battle)
                await asyncio.sleep(0.1)

        await asyncio.sleep(0.3)


# ══════════════════════════════════════════════════════════════════════════════
#  Stress test scenarios
# ══════════════════════════════════════════════════════════════════════════════

async def stress_s1_race_to_conquer(bots: list[Bot]) -> None:
    """S1 — All 4 bots try to conquer the SAME free zone simultaneously."""
    await log("STRESS", "S1: All bots race to conquer the same free zone at the same moment", "stress")

    zones = await bots[0].list_zones()
    free = [z for z in zones if not z.get("owner_clan_id")]
    if not free:
        await log("STRESS", "S1 skipped — no free zones available", "warn")
        return

    target = free[0]
    await log("STRESS", f"Target zone: '{target['name']}' ({target['id']})", "stress")

    results = await asyncio.gather(
        *[bot.conquer_zone(target) for bot in bots],
        return_exceptions=True,
    )
    winners = [bots[i].name for i, ok in enumerate(results) if ok is True]
    await log("STRESS", f"S1 result: conquer succeeded for → {winners or 'nobody'}", "stress")
    await record("stress_s1", "SYSTEM", {"target_zone": target["id"], "winners": winners})


async def stress_s2_simultaneous_attacks(bots: list[Bot]) -> None:
    """S2 — Two bots attack the same enemy zone at the same time."""
    await log("STRESS", "S2: Two bots attack the SAME zone simultaneously", "stress")

    zones = await bots[0].list_zones()
    # Find a zone owned by someone other than the last two bots
    attacker_a, attacker_b = bots[2], bots[3]
    target_zones = [
        z for z in zones
        if z.get("owner_clan_id")
        and z["owner_clan_id"] not in {attacker_a.clan_id, attacker_b.clan_id}
    ]
    if not target_zones:
        await log("STRESS", "S2 skipped — no suitable enemy zone found", "warn")
        return

    target = random.choice(target_zones)
    await log("STRESS", f"Both {attacker_a.name} and {attacker_b.name} attack '{target['name']}'", "stress")

    battles = await asyncio.gather(
        attacker_a.initiate_battle(target),
        attacker_b.initiate_battle(target),
        return_exceptions=True,
    )
    succeeded = sum(1 for b in battles if isinstance(b, dict) and b is not None)
    await log(
        "STRESS",
        f"S2 result: {succeeded}/2 battles created (expected exactly 1 — the rest get 'already ongoing')",
        "stress",
    )
    await record("stress_s2", "SYSTEM", {
        "target_zone": target["id"], "battles_created": succeeded
    })

    # Resolve whichever battle was created
    for b in battles:
        if isinstance(b, dict) and b is not None:
            actor = attacker_a if attacker_a.clan_id == b.get("attacker_clan_id") else attacker_b
            await asyncio.sleep(0.1)
            await actor.resolve_battle(b)


async def stress_s3_unauthorized_resolve(bots: list[Bot]) -> None:
    """S3 — Bot that is NOT a participant tries to resolve a battle (403 expected)."""
    await log("STRESS", "S3: Non-participant bot tries to resolve a battle (403 expected)", "stress")

    # Bot 0 attacks a zone owned by Bot 1
    zones = await bots[0].list_zones()
    bot1_zones = [z for z in zones if z.get("owner_clan_id") == bots[1].clan_id]
    if not bot1_zones:
        await log("STRESS", "S3 skipped — Bot 1 owns no zones", "warn")
        return

    target = bot1_zones[0]
    battle = await bots[0].initiate_battle(target)
    if not battle:
        await log("STRESS", "S3 skipped — could not start battle", "warn")
        return

    await log("STRESS", f"Battle {battle['id'][:8]}… started. Now bot {bots[2].name} (outsider) tries to resolve…", "stress")
    result = await bots[2].resolve_battle(battle)
    if result is None:
        await log("STRESS", "S3 PASSED — outsider correctly rejected with 403", "ok")
    else:
        await log("STRESS", "S3 FAILED — outsider was allowed to resolve (logic bug!)", "error")

    # Clean up: real participant resolves it
    await asyncio.sleep(0.1)
    await bots[0].resolve_battle(battle)


# ══════════════════════════════════════════════════════════════════════════════
#  Final report
# ══════════════════════════════════════════════════════════════════════════════

async def print_final_report(bots: list[Bot], client: AsyncClient) -> None:
    print("\n" + "═" * 72)
    print(f"{BOLD}  FINAL REPORT{RESET}")
    print("═" * 72)

    # Zone ownership
    r = await client.get("/api/v1/zones/")
    if r.status_code == 200:
        zones = r.json()
        owned = [z for z in zones if z.get("owner_clan_id")]
        clan_counts: dict[str, int] = {}
        for z in owned:
            clan_counts[z["owner_clan_id"]] = clan_counts.get(z["owner_clan_id"], 0) + 1

        print(f"\n  Zone ownership ({len(owned)}/{len(zones)} zones claimed):")
        for bot in bots:
            count = clan_counts.get(bot.clan_id, 0)
            bar = "█" * count
            print(f"    {COLORS[bot.name]}{bot.name:14s}{RESET} {bot.clan_name:12s}  {bar} {count} zones")

    # Power standings
    r2 = await client.get("/api/v1/users/leaderboard?limit=10")
    if r2.status_code == 200:
        lb = r2.json()
        print(f"\n  Power leaderboard (top {len(lb)}):")
        for i, u in enumerate(lb, 1):
            name = next((b.name for b in bots if b.user_id == u["id"]), u.get("name", "?"))
            color = COLORS.get(name, RESET)
            print(f"    #{i}  {color}{name:14s}{RESET}  {u['power_points']:>6} power  "
                  f"{u['steps_total']:>8,} steps  {u.get('gold', 0):>4} gold")

    # Combat log summary
    print(f"\n  Combat log ({len(_combat_log)} events):")
    event_counts: dict[str, int] = {}
    for e in _combat_log:
        event_counts[e["event"]] = event_counts.get(e["event"], 0) + 1
    for ev, cnt in sorted(event_counts.items(), key=lambda x: -x[1]):
        print(f"    {ev:25s}  {cnt:>3}x")

    # Concurrency / logic errors
    errors = [e for e in _combat_log if "fail" in e["event"]]
    print(f"\n  Concurrency / logic errors detected: {len(errors)}")
    for e in errors:
        print(f"    [{e['ts'][11:19]}] {e['actor']:14s} {e['event']:25s}  {e.get('reason','')[:60]}")

    print("\n" + "═" * 72 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    # Seed Valencia zones manually — ASGITransport skips FastAPI lifespan hooks.
    from cloudrisk_api.database.almacen_en_memoria import seed_zones
    seed_zones()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # ── Instantiate bots ─────────────────────────────────────────────────
        bots = [
            Bot("CONQUISTADOR", "Clan Alfa",  "#ff6200", "conquistador", client),
            Bot("INVASOR",      "Clan Beta",  "#ff0033", "invasor",      client),
            Bot("CORREDOR",     "Clan Gamma", "#aaff00", "corredor",     client),
            Bot("DEFENSOR",     "Clan Delta", "#00aaff", "defensor",     client),
        ]

        print("\n" + "═" * 72)
        print(f"{BOLD}  CloudRISK — BOT SIMULATION{RESET}")
        print(f"  {len(bots)} bots  |  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("═" * 72 + "\n")

        # ── Phase 0: Registration ─────────────────────────────────────────────
        await log("SYSTEM", "Phase 0 — Registering all bots (sequential to avoid name clashes)")
        for bot in bots:
            await bot.setup()
            await asyncio.sleep(0.05)

        # ── Phase 1: Individual strategies (concurrent) ───────────────────────
        await log("SYSTEM", "\nPhase 1 — All 4 bots run their strategies simultaneously\n")
        await asyncio.gather(
            run_conquistador(bots[0], rounds=4),
            run_invasor(bots[1],      rounds=4),
            run_corredor(bots[2],     rounds=4),
            run_defensor(bots[3],     rounds=4),
        )

        # ── Phase 2: Stress tests ─────────────────────────────────────────────
        await log("SYSTEM", "\nPhase 2 — Stress tests\n")
        await stress_s1_race_to_conquer(bots)
        await asyncio.sleep(0.2)
        await stress_s2_simultaneous_attacks(bots)
        await asyncio.sleep(0.2)
        await stress_s3_unauthorized_resolve(bots)

        # ── Final report ──────────────────────────────────────────────────────
        await print_final_report(bots, client)


if __name__ == "__main__":
    t0 = time.perf_counter()
    asyncio.run(main())
    elapsed = time.perf_counter() - t0
    print(f"Simulation completed in {elapsed:.2f}s\n")
