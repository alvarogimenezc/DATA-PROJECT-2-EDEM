"""
Tests for backend/cloudrisk_api/endpoints/ejercitos.py.

Covers:
- GET /balance
- POST /place (legacy — /actions/place is the contract path)
- GET /locations
- POST /fortify
"""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_balance_requires_auth(client):
    r = client.get("/api/v1/armies/balance")
    assert r.status_code == 401


def test_balance_returns_shape(client, registered_user):
    """Balance should include counts, earnings, limits."""
    r = client.get("/api/v1/armies/balance", headers=_auth(registered_user["token"]))
    assert r.status_code == 200
    body = r.json()
    # Fields returned by the current implementation:
    # {armies_available, armies_earned_today, armies_total_earned, max_per_zone}
    assert "armies_available" in body
    assert "armies_earned_today" in body
    assert "armies_total_earned" in body
    assert "max_per_zone" in body


def test_locations_requires_auth(client):
    r = client.get("/api/v1/armies/locations")
    assert r.status_code == 401


def test_locations_returns_valencia(client, registered_user):
    """All ~87 Valencia zones returned with garrison info."""
    r = client.get("/api/v1/armies/locations", headers=_auth(registered_user["token"]))
    assert r.status_code == 200
    zones = r.json()
    assert isinstance(zones, list)
    assert 80 <= len(zones) <= 90
    z = zones[0]
    assert "location_id" in z
    assert "name" in z
    assert "total_armies" in z
    assert "garrisons" in z


def test_place_rejects_nonpositive_amount(client, registered_user):
    """/armies/place with amount=0 → 400 (Pydantic gt=0)."""
    r = client.post(
        "/api/v1/armies/place",
        json={"location_id": "zona-russafa", "amount": 0},
        headers=_auth(registered_user["token"]),
    )
    assert r.status_code in (400, 422)


def test_fortify_requires_owned_source(client, registered_user):
    """Can't fortify from a zone you don't own."""
    r = client.post(
        "/api/v1/armies/fortify",
        json={"from_location_id": "zona-russafa", "to_location_id": "zona-centro", "amount": 1},
        headers=_auth(registered_user["token"]),
    )
    # Either 400 (not yours) or 404 (zone not found) is acceptable
    assert r.status_code in (400, 404)
