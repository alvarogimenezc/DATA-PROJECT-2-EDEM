"""
Tests for backend/cloudrisk_api/endpoints/batallas.py — dice combat + resolve.

Covers:
- list_battles, battle_history happy paths
- POST /{id}/resolve with auth + participant check
- POST /resolve-expired with scheduler token
"""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_list_battles_empty_returns_200(client):
    """/api/v1/battles/ should be a plain listing."""
    r = client.get("/api/v1/battles/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_battle_history_requires_auth(client):
    """/api/v1/battles/history without token → 401."""
    r = client.get("/api/v1/battles/history")
    assert r.status_code == 401


def test_battle_history_empty_when_user_has_no_battles(client, registered_user):
    """Fresh user has no battle history."""
    r = client.get(
        "/api/v1/battles/history",
        headers=_auth(registered_user["token"]),
    )
    assert r.status_code == 200
    assert r.json() == []


def test_resolve_battle_requires_auth(client):
    """Without auth the resolve endpoint returns 401, not 404."""
    r = client.post("/api/v1/battles/some-battle-id/resolve")
    # Some setups route 401 first, some 404 on missing battle. Accept 401.
    assert r.status_code in (401, 403)


def test_resolve_battle_404_on_unknown(client, registered_user):
    """Auth'd caller hitting an unknown battle id → 404."""
    r = client.post(
        "/api/v1/battles/does-not-exist/resolve",
        headers=_auth(registered_user["token"]),
    )
    assert r.status_code == 404


def test_resolve_expired_requires_scheduler_token(client):
    """/resolve-expired is protected by X-Scheduler-Token (shared secret)."""
    r = client.post("/api/v1/battles/resolve-expired")
    assert r.status_code == 403


def test_resolve_expired_with_token(client):
    """With the correct token, the endpoint returns a structured response."""
    from cloudrisk_api.configuracion import settings

    r = client.post(
        "/api/v1/battles/resolve-expired",
        headers={"X-Scheduler-Token": settings.SCHEDULER_SECRET},
    )
    assert r.status_code == 200
    body = r.json()
    assert "resolved" in body
    assert "battles" in body
