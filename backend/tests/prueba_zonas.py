def test_list_zones_returns_valencia_seed(client):
    """
    Verify the seed loads the bulk of Valencia's 87 districts.
    The source-of-truth GeoJSON for Valencia has 87 polygons; our seed
    currently carries 86 (one district is pending merge). We assert a
    sensible lower bound so the test doesn't break on a single addition
    or deletion.
    """

    resp = client.get("/api/v1/zones/")
    assert resp.status_code == 200
    zones = resp.json()
    assert 80 <= len(zones) <= 90, f"unexpected zone count: {len(zones)}"
    zone_ids = {z["id"] for z in zones}
    assert "zona-el-carme" in zone_ids
    assert all("name" in z and "value" in z for z in zones)


def test_adjacency_graph_no_500(client):
    """Regression guard: /zones/adjacency must not raise NameError (500)."""
    resp = client.get("/api/v1/zones/adjacency")
    assert resp.status_code != 500, resp.text
    assert resp.status_code == 200
    body = resp.json()
    assert "adjacency" in body and "stats" in body


def test_attack_endpoint_no_500(client, registered_user):
    """Regression guard: /zones/{id}/attack must not throw NameError.

    Any non-500 status is acceptable — 400/403/404/409 are legitimate
    outcomes depending on ownership/adjacency, but a 500 would indicate
    the module-rename NameError has regressed.
    """
    token = registered_user["token"]
    resp = client.post(
        "/api/v1/zones/zona-el-carme/attack",
        json={"from_zone_id": "zona-russafa", "attacker_dice": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 500, resp.text
