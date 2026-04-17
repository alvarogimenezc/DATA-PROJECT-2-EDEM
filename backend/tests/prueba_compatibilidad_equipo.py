"""
Tests for backend/cloudrisk_api/endpoints/compatibilidad_equipo.py — THE CONTRACT.

This router MUST match alvarogimenezc/DATA-PROJECT-2-EDEM exactly:
    GET  /api/v1/state/player/{player_id}
    GET  /api/v1/state/locations
    POST /api/v1/actions/place

If any of these tests regresses, the team integration breaks.
"""
from __future__ import annotations


def test_state_player_returns_contract_shape(client, registered_user):
    """The response must contain armies, total_steps, updated_at, player_id."""
    # Look up the freshly registered user's id via /users/me
    r = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    assert r.status_code in (200, 201)
    user_id = r.json()["id"]

    # Hit the contract endpoint
    r = client.get(f"/api/v1/state/player/{user_id}")
    assert r.status_code in (200, 201)
    body = r.json()

    # Contract fields — every one required.
    assert body["player_id"] == user_id
    assert isinstance(body["armies"], int)
    assert isinstance(body["total_steps"], int)
    assert "updated_at" in body


def test_state_player_404_on_unknown(client):
    """Unknown player_id → 404."""
    r = client.get("/api/v1/state/player/does-not-exist-xyz")
    assert r.status_code == 404


def test_state_locations_returns_list(client):
    """GET /state/locations returns a list of Location dicts."""
    r = client.get("/api/v1/state/locations")
    assert r.status_code in (200, 201)
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 80          # Valencia has ~87 zones
    first = data[0]

    # Contract minimum
    assert "location_id" in first
    assert "armies" in first
    assert "owner" in first
    assert "updated_at" in first


def test_state_locations_includes_frontend_extensions(client):
    """Our richer fields (name, garrisons, value_score) are present."""
    r = client.get("/api/v1/state/locations")
    data = r.json()
    first = data[0]

    # Frontend-facing extras (optional in the Pydantic model, populated here)
    assert "name" in first
    assert "total_armies" in first
    assert "owner_clan_id" in first
    assert "value_score" in first


def test_actions_place_with_explicit_player_id(client, registered_user):
    """The contract endpoint with explicit player_id in body (strict shape)."""
    # Get the user id
    r = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    user_id = r.json()["id"]

    # Sync some steps so the user has power to place
    r = client.post(
        "/api/v1/steps/sync",
        json={"steps": 10000},
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    assert r.status_code in (200, 201)

    # Find a zone
    zones = client.get("/api/v1/state/locations").json()
    zone_id = zones[0]["location_id"]

    # Place using CONTRACT shape (player_id + armies fields)
    r = client.post(
        "/api/v1/actions/place",
        json={"player_id": user_id, "location_id": zone_id, "armies": 2},
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "action_id" in body
    assert "remaining_armies" in body


def test_actions_place_with_auth_fallback(client, registered_user):
    """Frontend shortcut: no player_id in body, JWT provides it."""
    r = client.post(
        "/api/v1/steps/sync",
        json={"steps": 10000},
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    assert r.status_code in (200, 201)

    zones = client.get("/api/v1/state/locations").json()
    zone_id = zones[0]["location_id"]

    # Legacy 'amount' field also accepted for back-compat with /armies/place
    r = client.post(
        "/api/v1/actions/place",
        json={"location_id": zone_id, "amount": 1},
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    assert r.status_code in (200, 201)


def test_actions_place_rejects_without_player_id_and_without_auth(client):
    """Neither body player_id nor JWT → 400."""
    r = client.post(
        "/api/v1/actions/place",
        json={"location_id": "zona-russafa", "armies": 1},
    )
    assert r.status_code == 400
    assert "player_id" in r.json()["detail"].lower()


def test_actions_place_rejects_nonpositive_armies(client, registered_user):
    """armies must be > 0."""
    r = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    user_id = r.json()["id"]

    r = client.post(
        "/api/v1/actions/place",
        # Pydantic Field(gt=0) catches this BEFORE our handler runs
        json={"player_id": user_id, "location_id": "zona-russafa", "armies": 0},
    )
    assert r.status_code == 422   # Pydantic validation error


def test_actions_place_404_on_unknown_location(client, registered_user):
    """Unknown zone → 404."""
    r = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    user_id = r.json()["id"]
    r = client.post(
        "/api/v1/steps/sync",
        json={"steps": 10000},
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )

    r = client.post(
        "/api/v1/actions/place",
        json={"player_id": user_id, "location_id": "zona-no-existe", "armies": 1},
    )
    assert r.status_code == 404
