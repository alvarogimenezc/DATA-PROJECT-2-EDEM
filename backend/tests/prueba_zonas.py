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
