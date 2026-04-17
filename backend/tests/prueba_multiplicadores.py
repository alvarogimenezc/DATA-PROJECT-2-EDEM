"""End-to-end test of the environmental multiplier flow."""
from cloudrisk_api.services import multiplicadores as multipliers


def test_default_neutral():
    multipliers.reset()
    s = multipliers.current()
    assert s.air == 1.0
    assert s.weather == 1.0
    assert s.combined == 1.0


def test_air_message_updates_only_air():
    multipliers.reset()
    multipliers.update_from_message({
        "type": "air_quality",
        "ts": "2026-04-14T20:00:00+00:00",
        "indice_multiplicador_aire": 1.275,
    })
    s = multipliers.current()
    assert s.air == 1.275
    assert s.weather == 1.0
    assert s.combined == 1.275


def test_weather_message_updates_only_weather():
    multipliers.reset()
    multipliers.update_from_message({
        "type": "weather",
        "ts": "2026-04-14T20:00:00+00:00",
        "indice_multiplicador_tiempo": 0.8,
    })
    s = multipliers.current()
    assert s.air == 1.0
    assert s.weather == 0.8
    assert s.combined == 0.8


def test_combined_is_clamped():
    multipliers.reset()
    multipliers.update_from_message({"type": "air_quality", "indice_multiplicador_aire": 1.5})
    multipliers.update_from_message({"type": "weather", "indice_multiplicador_tiempo": 1.5})
    assert multipliers.current().combined == 2.25   # 1.5 * 1.5

    multipliers.update_from_message({"type": "air_quality", "indice_multiplicador_aire": 0.6})
    multipliers.update_from_message({"type": "weather", "indice_multiplicador_tiempo": 0.6})
    assert multipliers.current().combined == 0.36   # 0.6 * 0.6


def test_endpoints_via_client(client):
    from cloudrisk_api.configuracion import settings
    multipliers.reset()
    # Ingest one air message. /ingest is gated by X-Scheduler-Token (shared
    # secret). Production Secret Manager injects it; tests read from settings.
    r = client.post(
        "/api/v1/multipliers/ingest",
        json={
            "type": "air_quality",
            "ts": "2026-04-14T20:00:00+00:00",
            "indice_multiplicador_aire": 1.275,
        },
        headers={"X-Scheduler-Token": settings.SCHEDULER_SECRET},
    )
    assert r.status_code == 204


def test_ingest_rejects_without_token(client):
    """Without the scheduler token, /ingest must return 403 (security)."""
    r = client.post("/api/v1/multipliers/ingest", json={
        "type": "air_quality",
        "ts": "2026-04-14T20:00:00+00:00",
        "indice_multiplicador_aire": 1.0,
    })
    assert r.status_code == 403

    # Read it back
    r = client.get("/api/v1/multipliers/")
    assert r.status_code == 200
    body = r.json()
    assert body["air"] == 1.275
    assert body["weather"] == 1.0
    assert body["combined"] == 1.275
