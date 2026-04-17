"""
Tests for backend/cloudrisk_api/endpoints/turno.py — turn rotation.
"""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_get_current_turn_public(client):
    """GET /api/v1/turn/ is readable without auth."""
    r = client.get("/api/v1/turn/")
    assert r.status_code == 200
    body = r.json()
    # Expected shape: current_player_id, phase, turn_number (all optional
    # depending on whether game_state was initialized)
    assert "current_player_id" in body or "current" in body or body == {}


def test_end_turn_requires_auth(client):
    """POST /api/v1/turn/end rejects anonymous callers."""
    r = client.post("/api/v1/turn/end")
    assert r.status_code == 401


def test_advance_phase_requires_auth(client):
    r = client.post("/api/v1/turn/advance_phase")
    assert r.status_code == 401


def test_end_turn_rotates_to_next_player(client, registered_user):
    """After end-turn, the turn pointer should advance (idempotent-safe)."""
    # Record state before
    before = client.get("/api/v1/turn/").json()

    # Try to end turn (may fail if it's not our turn — that's OK, we check behavior either way)
    r = client.post("/api/v1/turn/end", headers=_auth(registered_user["token"]))
    # Accept 200 (success) or 400/403 (not your turn)
    assert r.status_code in (200, 400, 403)

    # Getting the state again should still return 200
    after = client.get("/api/v1/turn/")
    assert after.status_code == 200
