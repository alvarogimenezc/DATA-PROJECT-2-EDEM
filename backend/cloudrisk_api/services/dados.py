"""Risk combat dice resolution — official rules.

    Attacker rolls 1, 2 or 3 dice. Must have at least (dice+1) armies in the
    source zone (must leave 1 behind).
    Defender rolls 1 or 2 dice. 2 requires >=2 armies in the zone.
    Pair the highest dice; attacker wins ties for the defender. Each loss
    costs the losing side 1 army. If both rolled >=2 dice, the 2nd-highest
    pair is compared the same way.

See https://www.hasbro.com/common/instruct/risk.pdf
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CombatResult:
    attacker_rolls: list[int]
    defender_rolls: list[int]
    attacker_losses: int
    defender_losses: int


def resolve(attacker_dice: int, defender_dice: int, rng: Optional[random.Random] = None) -> CombatResult:
    """Roll the dice and return casualties for one attack round."""
    if attacker_dice not in (1, 2, 3):
        raise ValueError(f"attacker_dice must be 1, 2, or 3 (got {attacker_dice})")
    if defender_dice not in (1, 2):
        raise ValueError(f"defender_dice must be 1 or 2 (got {defender_dice})")

    r = rng or random
    attacker_rolls = sorted((r.randint(1, 6) for _ in range(attacker_dice)), reverse=True)
    defender_rolls = sorted((r.randint(1, 6) for _ in range(defender_dice)), reverse=True)

    att_losses = 0
    def_losses = 0
    pairs = min(len(attacker_rolls), len(defender_rolls))
    for i in range(pairs):
        if attacker_rolls[i] > defender_rolls[i]:
            def_losses += 1
        else:  # tie or defender higher
            att_losses += 1

    return CombatResult(
        attacker_rolls=attacker_rolls,
        defender_rolls=defender_rolls,
        attacker_losses=att_losses,
        defender_losses=def_losses,
    )
