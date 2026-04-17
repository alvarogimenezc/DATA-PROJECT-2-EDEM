"""HTTP surface for the environmental multipliers cache.

Two endpoints, intentionally tiny:

  GET  /api/v1/multipliers          → current snapshot (read by frontend HUD,
                                       dashboard, and game logic)
  POST /api/v1/multipliers/ingest   → ingestor entry point (called by the
                                       weather/air scripts when running with
                                       BACKEND_INGEST_URL set)
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from cloudrisk_api.configuracion import settings
from cloudrisk_api.services import multiplicadores as mults


router = APIRouter(prefix="/multipliers", tags=["multipliers"])


class MultiplierResponse(BaseModel):
    air: float
    weather: float
    combined: float
    air_ts: str | None
    weather_ts: str | None


@router.get("/", response_model=MultiplierResponse, summary="Current air × weather multipliers")
def get_current():
    s = mults.current()
    return MultiplierResponse(
        air=s.air, weather=s.weather, combined=s.combined,
        air_ts=s.air_ts, weather_ts=s.weather_ts,
    )


@router.post("/ingest", status_code=204, summary="Receive one message from the ingestors")
def ingest(
    payload: dict[str, Any],
    x_scheduler_token: Optional[str] = Header(None, alias="X-Scheduler-Token"),
):
    # Shared-secret auth — ingestors set the header from Secret Manager.
    # Rejecting unauthenticated calls prevents anyone from spiking multipliers.
    if x_scheduler_token != settings.SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: missing/invalid scheduler token")
    if not isinstance(payload, dict) or "type" not in payload:
        raise HTTPException(status_code=400, detail="payload must be {type, ...}")
    try:
        mults.update_from_message(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
