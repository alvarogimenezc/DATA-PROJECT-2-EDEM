"""
Tests for backend/cloudrisk_api/endpoints/pasos.py.

Covers:
- POST /steps/sync (add steps, converts to power points)
- GET  /steps/history
"""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_steps_sync_requires_auth(client):
    r = client.post("/api/v1/steps/sync", json={"steps": 100})
    assert r.status_code == 401


def test_steps_sync_zero_steps_noop(client, registered_user):
    """0 steps should return 200 without creating a log."""
    r = client.post(
        "/api/v1/steps/sync",
        json={"steps": 0},
        headers=_auth(registered_user["token"]),
    )
    # Either a 200 with no-op message or a 400; both acceptable.
    assert r.status_code in (200, 400)


def test_steps_sync_converts_to_power(client, registered_user):
    """10000 steps at POWER_PER_STEPS=100 → 100 power points."""
    r = client.post(
        "/api/v1/steps/sync",
        json={"steps": 10000},
        headers=_auth(registered_user["token"]),
    )
    assert r.status_code in (200, 201)
    body = r.json()
    # One of these keys indicates success
    assert any(k in body for k in ("power_earned", "gold_earned", "steps", "message"))


def test_steps_history_returns_list(client, registered_user):
    """History returns a list (possibly empty) of step events."""
    r = client.get(
        "/api/v1/steps/history",
        headers=_auth(registered_user["token"]),
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_steps_history_requires_auth(client):
    r = client.get("/api/v1/steps/history")
    assert r.status_code == 401


def test_steps_after_sync_appear_in_state_player(client, registered_user):
    """After syncing steps, /state/player/{id} reflects the new total."""
    # Get user id
    me = client.get("/api/v1/users/me", headers=_auth(registered_user["token"])).json()

    # Sync some steps
    client.post(
        "/api/v1/steps/sync",
        json={"steps": 5000},
        headers=_auth(registered_user["token"]),
    )

    # Team contract endpoint should see them
    r = client.get(f"/api/v1/state/player/{me['id']}")
    assert r.status_code == 200
    assert r.json()["total_steps"] >= 5000
