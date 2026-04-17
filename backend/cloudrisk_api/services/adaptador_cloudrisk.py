"""Adapter for the team's CloudRISK backend (alvarogimenezc/DATA-PROJECT-2-EDEM).

The team backend exposes a small surface (3 endpoints) that overlaps with
ours but uses different paths and field names:

  team                                 ←→  ours
  ───────────────────────────────────  ←─→ ────────────────────────────
  GET  /api/v1/state/locations         ←→  GET  /api/v1/zones/
  GET  /api/v1/state/player/{id}       ←→  GET  /api/v1/users/me
  POST /api/v1/actions/place           ←→  POST /api/v1/armies/place

When the env var ``CLOUDRISK_API_URL`` is set (e.g. to
``https://cloudrisk-api-xxxxx.a.run.app``), this module's helpers proxy
read/write requests to that backend so our routers can fall back to it
on demand. When the env var is unset, the helpers no-op (return None /
raise NotConfigured) and our local store is used as today.

This is an *adapter*, not a replacement: our backend keeps owning auth,
clans, battles, steps, websockets, etc. — none of which exist on the
team side. The adapter only shows up where the team backend has a
real story (state/locations + actions/place).

NOTE: kept self-contained on purpose. To wire it into a router, do:

    from cloudrisk_api.services import adaptador_cloudrisk as cr
    if cr.is_enabled():
        try:
            return cr.get_locations()
        except cr.AdapterError:
            pass  # fall through to local store
"""
from __future__ import annotations

import os
from typing import Any

# httpx is already a project dependency (used by tests). We use it sync here
# to keep callers ergonomic; switch to the async client only if a router
# becomes a hot path under load.
try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None


class AdapterError(RuntimeError):
    """Raised when the upstream CloudRISK backend returns a non-2xx response."""


class NotConfigured(RuntimeError):
    """Raised when CLOUDRISK_API_URL is not set."""


def base_url() -> str | None:
    """Return the configured base URL (without trailing slash) or None."""
    url = os.environ.get("CLOUDRISK_API_URL", "").strip().rstrip("/")
    return url or None


def is_enabled() -> bool:
    """True when the adapter is configured and httpx is importable."""
    return bool(base_url()) and httpx is not None


def _client() -> "httpx.Client":
    if httpx is None:
        raise NotConfigured("httpx not installed")
    url = base_url()
    if not url:
        raise NotConfigured("CLOUDRISK_API_URL not set")
    return httpx.Client(base_url=url, timeout=5.0)


def get_locations() -> list[dict[str, Any]]:
    """Fetch locations from the team backend.

    Returns a list of dicts shaped like:
        {"location_id": str, "armies": int, "owner": str | None, "updated_at": str | None}
    """
    with _client() as c:
        r = c.get("/api/v1/state/locations")
    if r.status_code != 200:
        raise AdapterError(f"GET /state/locations → {r.status_code}: {r.text[:200]}")
    return r.json()


def get_player_state(player_id: str) -> dict[str, Any]:
    """Fetch a player's balance from the team backend."""
    with _client() as c:
        r = c.get(f"/api/v1/state/player/{player_id}")
    if r.status_code != 200:
        raise AdapterError(f"GET /state/player/{player_id} → {r.status_code}: {r.text[:200]}")
    return r.json()


def place_armies(player_id: str, location_id: str, armies: int) -> dict[str, Any]:
    """Forward a 'place armies' action to the team backend."""
    with _client() as c:
        r = c.post(
            "/api/v1/actions/place",
            json={"player_id": player_id, "location_id": location_id, "armies": armies},
        )
    if r.status_code >= 400:
        raise AdapterError(f"POST /actions/place → {r.status_code}: {r.text[:200]}")
    return r.json()
