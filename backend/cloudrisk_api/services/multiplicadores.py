"""In-memory cache of the latest air-quality and weather multipliers.

The two ingestors at weather_airq/ POST messages here every 30 s. Game logic
(routers/armies.py::place_armies) reads .current() to scale troop deployments.

Thread-safe (FastAPI runs handlers in a thread pool); the writes are tiny so
a plain RLock is enough.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Snapshot:
    """A point-in-time view of both multipliers."""
    air: float = 1.0           # neutral default until the air ingestor pings us
    weather: float = 1.0       # neutral default until the weather ingestor pings us
    air_ts: Optional[str] = None
    weather_ts: Optional[str] = None
    air_payload: dict = field(default_factory=dict)
    weather_payload: dict = field(default_factory=dict)

    @property
    def combined(self) -> float:
        """The product applied to deployments: air * weather, clamped [0.36, 2.25]."""
        return round(max(0.36, min(2.25, self.air * self.weather)), 3)


_lock = threading.RLock()
_state: Snapshot = Snapshot()


def current() -> Snapshot:
    with _lock:
        return _state


def update_from_message(message: dict) -> Snapshot:
    """Apply one ingestor message ({type: 'air_quality'|'weather', ...}) to the cache."""
    global _state
    msg_type = message.get("type")
    if msg_type not in ("air_quality", "weather"):
        raise ValueError(f"unsupported multiplier message type: {msg_type!r}")

    with _lock:
        if msg_type == "air_quality":
            _state = Snapshot(
                air=float(message.get("indice_multiplicador_aire", 1.0)),
                weather=_state.weather,
                air_ts=message.get("ts"),
                weather_ts=_state.weather_ts,
                air_payload=message,
                weather_payload=_state.weather_payload,
            )
        else:  # weather
            _state = Snapshot(
                air=_state.air,
                weather=float(message.get("indice_multiplicador_tiempo", 1.0)),
                air_ts=_state.air_ts,
                weather_ts=message.get("ts"),
                air_payload=_state.air_payload,
                weather_payload=message,
            )
        return _state


def reset() -> None:
    """Test helper — wipe the cache."""
    global _state
    with _lock:
        _state = Snapshot()
