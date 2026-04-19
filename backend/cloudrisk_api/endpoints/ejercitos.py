"""Router: despliegue de tropas, balance, ubicaciones y fortificación."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cloudrisk_api.configuracion import MIN_GARRISON
from cloudrisk_api.database import usuarios as usuarios_repo, zonas as zonas_repo
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import multiplicadores as multipliers

import os
USE_LOCAL = os.environ.get("USE_LOCAL_STORE", "0") == "1"
if USE_LOCAL:
    from cloudrisk_api.database import almacen_en_memoria as store

router = APIRouter(prefix="/armies", tags=["armies"])


class PlaceRequest(BaseModel):
    location_id: str
    amount: int


class FortifyRequest(BaseModel):
    from_location_id: str
    to_location_id: str
    amount: int


def _get_garrisons():
    """Devuelve todos los datos de guarniciones desde las zonas (store en memoria para dev local)."""
    if USE_LOCAL:
        zones = store.doc_stream("zones")
    else:
        zones = zonas_repo.list_zones()
    return zones


@router.get("/balance")
def get_balance(current_user: dict = Depends(get_current_user)):
    """Devuelve el balance de tropas del usuario."""
    power = current_user.get("power_points", 0)
    steps = current_user.get("steps_total", 0)
    # Armies disponibles = power_points (cada 100 pasos = 1 army)
    # Simulamos un tope diario de 40 armies
    armies_available = power
    armies_earned_today = min(power, 40)
    return {
        "armies_available": armies_available,
        "armies_earned_today": armies_earned_today,
        "armies_total_earned": power,
        "max_per_zone": 40,
    }


@router.post("/place")
def place_armies(data: PlaceRequest, current_user: dict = Depends(get_current_user)):
    """Despliega tropas en una zona."""
    zone = zonas_repo.get_zone_by_id(data.location_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")

    user_power = current_user.get("power_points", 0)
    if data.amount > user_power:
        raise HTTPException(status_code=400, detail="No tienes suficientes tropas disponibles")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Cantidad inv\u00e1lida")

    # Aplica el multiplicador ambiental (calidad del aire × clima). Cuando
    # los ingestors todavía no han reportado, .combined queda en 1.0 (neutro).
    snap = multipliers.current()
    effective_amount = max(1, round(data.amount * snap.combined))

    # Actualiza la defensa de la zona y el poder del usuario
    current_defense = zone.get("defense_level", 0) or 0
    new_defense = min(current_defense + effective_amount, 40)
    zonas_repo.update_zone(data.location_id, {
        "defense_level": new_defense,
        "owner_clan_id": current_user.get("clan_id") or current_user["id"],
    })

    # El usuario paga la cantidad BASE (data.amount); el multiplicador le da
    # más (o menos) tropas efectivas sobre el terreno. Así un día soleado con
    # aire limpio premia el despliegue y una tormenta lo penaliza.
    new_power = max(0, user_power - data.amount)
    usuarios_repo.update_user(current_user["id"], {"power_points": new_power})

    return {
        "message": (
            f"Has desplegado {data.amount} tropas en {zone.get('name', data.location_id)} "
            f"(x{snap.combined} → {effective_amount} efectivas)."
        ),
        "zone_id": data.location_id,
        "new_defense": new_defense,
        "base_amount": data.amount,
        "effective_amount": effective_amount,
        "multiplier": snap.combined,
        "air_multiplier": snap.air,
        "weather_multiplier": snap.weather,
    }


@router.get("/locations")
def get_locations(current_user: dict = Depends(get_current_user)):
    """Devuelve todas las zonas con info de guarnición."""
    zones = _get_garrisons()
    result = []
    for z in zones:
        total_armies = z.get("defense_level", 0) or 0
        garrisons = {}
        owner = z.get("owner_clan_id")
        if owner == current_user.get("clan_id") or owner == current_user.get("id"):
            garrisons[current_user["id"]] = {"armies": total_armies}

        result.append({
            "location_id": z.get("id"),
            "id": z.get("id"),
            "name": z.get("name"),
            "total_armies": total_armies,
            "owner_clan_id": owner,
            "owner_clan_name": "",
            "owner_clan_color": "",
            "garrisons": garrisons,
            "value_score": z.get("value", 0),
        })
    return result


@router.post("/fortify")
def fortify(data: FortifyRequest, current_user: dict = Depends(get_current_user)):
    """Mueve tropas entre zonas propias."""
    from_zone = zonas_repo.get_zone_by_id(data.from_location_id)
    to_zone = zonas_repo.get_zone_by_id(data.to_location_id)

    if not from_zone or not to_zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")

    user_owner = current_user.get("clan_id") or current_user.get("id")
    if from_zone.get("owner_clan_id") != user_owner:
        raise HTTPException(status_code=403, detail="No controlas la zona de origen")

    from_armies = from_zone.get("defense_level", 0) or 0
    if from_armies - data.amount < MIN_GARRISON:
        raise HTTPException(
            status_code=400,
            detail=f"Debes dejar al menos {MIN_GARRISON} tropas en la zona de origen",
        )
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Cantidad inv\u00e1lida")

    # Mueve las tropas
    zonas_repo.update_zone(data.from_location_id, {
        "defense_level": from_armies - data.amount,
    })
    to_armies = to_zone.get("defense_level", 0) or 0
    zonas_repo.update_zone(data.to_location_id, {
        "defense_level": to_armies + data.amount,
        "owner_clan_id": user_owner,
    })

    return {
        "message": f"Movidas {data.amount} tropas de {from_zone.get('name')} a {to_zone.get('name')}.",
    }
