"""Tactical advisor: deterministic battle advice engine (zero external deps)."""

from __future__ import annotations


TACTICAL_TIPS = [
    "Focus your clan's power on a single zone before expanding to adjacent territory.",
    "Coordinate with your clan members — attack when most of them are walking nearby.",
    "Higher defense levels make zones harder to take. Prioritise low-defense targets first.",
    "Timing matters: launch attacks when the defending clan is least active.",
    "Accumulate power through steps before engaging a well-defended zone.",
]


def get_battle_advice(context: dict) -> str:
    atk = context.get("attacker_power", 0)
    dfn = context.get("defender_power", 0)
    defense_level = context.get("defense_level", 0)

    if atk > dfn * 1.5:
        return (
            f"Your clan has a strong power advantage ({atk} vs {dfn}). "
            "Press the attack — victory is likely if you maintain activity."
        )
    if dfn > atk * 1.5:
        return (
            f"The defenders overpower you ({dfn} vs {atk}). "
            "Rally your clan to walk more and build power before committing."
        )
    if defense_level >= 7:
        return (
            f"Zone defense is high ({defense_level}/10). "
            "Consider targeting a weaker zone first to build momentum."
        )
    idx = (atk + dfn + defense_level) % len(TACTICAL_TIPS)
    return TACTICAL_TIPS[idx]
