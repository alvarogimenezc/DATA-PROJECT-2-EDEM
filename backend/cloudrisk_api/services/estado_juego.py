"""In-memory turn-based game state.

Tracks whose turn it is, which phase they're in (reinforce → attack → fortify),
the turn counter, and the last combat result for the frontend's dice
animation.

The turn order is hard-coded to the 4 seeded lobby players (same rotation
the data_generator/bot_ia_riesgo.py assumes). For the demo that's enough;
when the game grows to N players we'll load the order from Firestore.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Literal, Optional


PHASES: tuple[str, ...] = ("reinforce", "attack", "fortify")
Phase = Literal["reinforce", "attack", "fortify"]


# Hard-coded lobby order — matches data/players.json ids.
DEFAULT_PLAYER_ORDER: list[str] = [
    "demo-player-001",  # Norte
    "demo-player-002",  # Sur
    "demo-player-003",  # Este
    "demo-player-004",  # Oeste
]


@dataclass(frozen=True)
class DiceResult:
    attacker_rolls: list[int]
    defender_rolls: list[int]
    attacker_losses: int
    defender_losses: int
    conquered: bool


@dataclass(frozen=True)
class GameState:
    current_player_id: str
    phase: Phase
    turn_number: int
    player_order: list[str]
    last_dice: Optional[DiceResult] = None

    def to_dict(self) -> dict:
        d = {
            "current_player_id": self.current_player_id,
            "phase": self.phase,
            "turn_number": self.turn_number,
            "player_order": list(self.player_order),
        }
        if self.last_dice:
            d["last_dice"] = {
                "attacker_rolls":   self.last_dice.attacker_rolls,
                "defender_rolls":   self.last_dice.defender_rolls,
                "attacker_losses":  self.last_dice.attacker_losses,
                "defender_losses":  self.last_dice.defender_losses,
                "conquered":        self.last_dice.conquered,
            }
        return d


_lock = threading.RLock()
_state: GameState = GameState(
    current_player_id=DEFAULT_PLAYER_ORDER[0],
    phase="reinforce",
    turn_number=1,
    player_order=DEFAULT_PLAYER_ORDER.copy(),
)


def current() -> GameState:
    with _lock:
        return _state


def is_players_turn(player_id: str) -> bool:
    with _lock:
        return _state.current_player_id == player_id


def advance_phase() -> GameState:
    """Move to the next phase in (reinforce → attack → fortify → next player's reinforce)."""
    global _state
    with _lock:
        idx = PHASES.index(_state.phase)
        if idx < len(PHASES) - 1:
            _state = GameState(
                current_player_id=_state.current_player_id,
                phase=PHASES[idx + 1],  # type: ignore[arg-type]
                turn_number=_state.turn_number,
                player_order=_state.player_order,
                last_dice=_state.last_dice,
            )
        else:
            # fortify → next player's reinforce
            pid_idx = _state.player_order.index(_state.current_player_id)
            next_idx = (pid_idx + 1) % len(_state.player_order)
            _state = GameState(
                current_player_id=_state.player_order[next_idx],
                phase="reinforce",
                turn_number=_state.turn_number + (1 if next_idx == 0 else 0),
                player_order=_state.player_order,
                last_dice=None,  # clear dice at the start of a new turn
            )
        return _state


def end_turn() -> GameState:
    """Skip straight to the next player's reinforce phase."""
    global _state
    with _lock:
        pid_idx = _state.player_order.index(_state.current_player_id)
        next_idx = (pid_idx + 1) % len(_state.player_order)
        _state = GameState(
            current_player_id=_state.player_order[next_idx],
            phase="reinforce",
            turn_number=_state.turn_number + (1 if next_idx == 0 else 0),
            player_order=_state.player_order,
            last_dice=None,
        )
        return _state


def record_dice(result: DiceResult) -> GameState:
    """Update the last-dice cache (called by the attack endpoint after rolling)."""
    global _state
    with _lock:
        _state = GameState(
            current_player_id=_state.current_player_id,
            phase=_state.phase,
            turn_number=_state.turn_number,
            player_order=_state.player_order,
            last_dice=result,
        )
        return _state


def reset() -> None:
    """Test helper — reset to turn 1, player 0, reinforce."""
    global _state
    with _lock:
        _state = GameState(
            current_player_id=DEFAULT_PLAYER_ORDER[0],
            phase="reinforce",
            turn_number=1,
            player_order=DEFAULT_PLAYER_ORDER.copy(),
        )
