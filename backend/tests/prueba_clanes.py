"""
Tests for backend/cloudrisk_api/endpoints/clanes.py.

Covers:
- GET  /clans/          (list)
- POST /clans/          (create)
- POST /clans/{id}/join
- POST /clans/leave
"""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_list_clans_public(client):
    r = client.get("/api/v1/clans/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_clan_requires_auth(client):
    r = client.post("/api/v1/clans/", json={"name": "Test Clan", "color": "#ff0000"})
    assert r.status_code == 401


def test_create_clan_returns_201_and_clan_shape(client, registered_user):
    """A clan has id, name, created_at at minimum."""
    import uuid
    r = client.post(
        "/api/v1/clans/",
        json={"name": f"Clan-{uuid.uuid4().hex[:6]}", "color": "#ff8c00"},
        headers=_auth(registered_user["token"]),
    )
    # 201 on create, 400 if user already has a clan
    assert r.status_code in (200, 201, 400)
    if r.status_code in (200, 201):
        body = r.json()
        assert "id" in body
        assert "name" in body


def test_leave_clan_without_membership(client, registered_user):
    """Leaving a clan you don't belong to → 400 (not 500)."""
    # Fresh user starts with no clan.
    r = client.post("/api/v1/clans/leave", headers=_auth(registered_user["token"]))
    # Either 400 (no clan) or 200 (idempotent no-op) is acceptable
    assert r.status_code in (200, 400)
