"""Router: Zone listing, cloudrisk, and real-time location detection."""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)


import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from cloudrisk_api.configuracion import settings, MIN_GARRISON
from cloudrisk_api.database import zonas as zonas_repo, clanes as clanes_repo, usuarios as usuarios_repo, publicador_pubsub as pubsub_publisher, batallas as batallas_repo
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import estado_juego as game_state, dados as dice, adyacencia as adjacency
from pydantic import BaseModel

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("/")
def list_zones():
    return zonas_repo.list_zones()


@router.get("/adjacency")
def get_adjacency_graph():
    """Grafo de vecinos {zone_id: [neighbor_ids]} precomputado del geojson.

    El frontend lo usa para:
      - Resaltar zonas atacables (adyacentes a las tuyas) en tiempo real.
      - Validar el ataque antes de enviarlo al backend.
    """
    adj = adjacency.get_adjacency()
    return {
        "adjacency": {zid: sorted(neighbors) for zid, neighbors in adj.items()},
        "stats": adjacency.stats(),
    }


@router.get("/{zone_id}")
def get_zone(zone_id: str):
    zone = zonas_repo.get_zone_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.post("/{zone_id}/conquer")
def conquer_zone(zone_id: str, current_user: dict = Depends(get_current_user)):
    """Claim a free zone atomically (no fight needed if owner is None).

    For contested zones, use POST /api/v1/zones/{zone_id}/attack instead —
    that runs the Risk dice combat.

    Atomicity: uses zonas_repo.conquer_zone_atomic() which wraps the
    read-check-write in a Firestore transaction (or a threading.Lock in
    local mode) so two players racing on the same zone cannot both win.
    """
    zone = zonas_repo.get_zone_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    # Pre-check: if the caller already owns the zone, idempotent success.
    owner = zone.get("owner_clan_id") or zone.get("owner")
    if owner and (owner == current_user["id"] or owner == current_user.get("clan_id")):
        return {"message": f"Zone '{zone['name']}' already yours.", "zone_id": zone_id}
    # Pre-check: if another clan owns it, block before the transaction.
    if owner:
        raise HTTPException(
            status_code=400,
            detail="This zone is enemy territory — use /attack instead.",
        )
    # Atomic claim. Returns False if someone else claimed it between our
    # read above and the transaction (narrow race window, but possible).
    claimed = zonas_repo.conquer_zone_atomic(
        zone_id=zone_id,
        clan_id=current_user["id"],
        conquered_at=datetime.utcnow().isoformat(),
    )
    if not claimed:
        raise HTTPException(
            status_code=409,
            detail="Zone was claimed by another player while you were acting",
        )
    return {"message": f"Zone '{zone['name']}' conquered!", "zone_id": zone_id}


class AttackRequest(BaseModel):
    from_zone_id: str
    attacker_dice: int   # 1, 2, or 3


def _validate_attack_request(req: "AttackRequest", zone_id: str, current_user: dict):
    """Valida pre-condiciones del ataque y devuelve `(source, target)`.

    Lanza `HTTPException` con 400/404 si algo falla. Tras esta función las
    zonas existen, las posee quien debe poseerlas y son adyacentes en el grafo.
    """
    if req.attacker_dice not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="attacker_dice must be 1, 2, or 3")

    source = zonas_repo.get_zone_by_id(req.from_zone_id)
    target = zonas_repo.get_zone_by_id(zone_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Zone not found")

    source_owner = source.get("owner_clan_id") or source.get("owner")
    target_owner = target.get("owner_clan_id") or target.get("owner")
    if source_owner != current_user["id"]:
        raise HTTPException(status_code=400, detail="You don't own the source zone")
    if target_owner == current_user["id"]:
        raise HTTPException(status_code=400, detail="You can't attack your own zone")

    # Regla Risk: la zona objetivo debe compartir frontera con la origen.
    # Excepción: si la origen no aparece en el grafo (caso extremo: zona sin
    # geojson), dejamos pasar el ataque para no bloquear partidas.
    adj_map = adjacency.get_adjacency()
    if req.from_zone_id in adj_map and zone_id not in adj_map[req.from_zone_id]:
        raise HTTPException(
            status_code=400,
            detail="Target zone is not adjacent to source. You can only attack neighboring territories.",
        )

    return source, target


def _conquer_free_zone(req: "AttackRequest", zone_id: str, source_armies: int,
                       target_owner, current_user: dict):
    """Caso especial: la zona objetivo no tiene defensores (`target_armies == 0`).

    El atacante transfiere `max(dados, MIN_GARRISON)` tropas y se queda con la
    zona sin tirada. Mantiene la invariante de garrison mínima del juego.
    """
    moved = max(req.attacker_dice, MIN_GARRISON)
    if source_armies <= moved:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {moved + 1} armies in source to claim this zone (have {source_armies})",
        )
    committed = zonas_repo.resolve_combat_atomic(
        source_id=req.from_zone_id,
        target_id=zone_id,
        attacker_clan=current_user["id"],
        expected_source_armies=source_armies,
        expected_target_owner=target_owner,
        expected_target_armies=0,
        new_source_armies=source_armies - moved,
        new_target_armies=moved,
        conquered=True,
        conquered_at=datetime.utcnow().isoformat(),
    )
    if not committed:
        raise HTTPException(status_code=409, detail="Zone state changed during combat; retry")
    return {
        "conquered": True,
        "attacker_rolls": [], "defender_rolls": [],
        "attacker_losses": 0, "defender_losses": 0,
        "source_armies_after": source_armies - moved,
        "target_armies_after": moved,
        "turn_violation": not game_state.is_players_turn(current_user["id"]),
    }


@router.post("/{zone_id}/attack")
def attack_zone(zone_id: str, req: AttackRequest, current_user: dict = Depends(get_current_user)):
    """Attack a contested zone with Risk dice rules.

    Turn check (soft): if it's not the caller's turn the response still
    resolves combat so solo-play doesn't dead-lock, but the response
    includes turn_violation=True so the UI can nag the user.
    """
    source, target = _validate_attack_request(req, zone_id, current_user)
    target_owner = target.get("owner_clan_id") or target.get("owner")

    source_armies = int(source.get("defense_level") or 0)
    target_armies = int(target.get("defense_level") or 0)
    # El atacante debe dejar al menos 1 ejército en la origen.
    if source_armies <= req.attacker_dice:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {req.attacker_dice + 1} armies in source (have {source_armies})",
        )

    # Camino corto: la zona objetivo está libre (sin defensores).
    if target_armies == 0:
        return _conquer_free_zone(req, zone_id, source_armies, target_owner, current_user)

    # Combate Risk normal — defensor tira 2 dados si tiene ≥ 2 ejércitos.
    defender_dice = 2 if target_armies >= 2 else 1
    combat = dice.resolve(req.attacker_dice, defender_dice)

    new_source = source_armies - combat.attacker_losses
    new_target = target_armies - combat.defender_losses
    conquered = new_target <= 0

    if conquered:
        # Si conquista, hay que mover al menos los dados tirados; además
        # respetamos la invariante de MIN_GARRISON en la zona tomada.
        moved = max(req.attacker_dice, MIN_GARRISON)
        new_source -= moved
        new_target = moved

    # Update atómico de AMBAS zonas con concurrencia optimista — si el estado
    # de cualquiera cambió desde la lectura, devolvemos 409 para que el
    # cliente reintente con la nueva foto.
    committed = zonas_repo.resolve_combat_atomic(
        source_id=req.from_zone_id,
        target_id=zone_id,
        attacker_clan=current_user["id"],
        expected_source_armies=source_armies,
        expected_target_owner=target_owner,
        expected_target_armies=target_armies,
        new_source_armies=new_source,
        new_target_armies=new_target,
        conquered=conquered,
        conquered_at=datetime.utcnow().isoformat(),
    )
    if not committed:
        raise HTTPException(status_code=409, detail="Zone state changed during combat; retry")

    # Cache para que el frontend pueda animar los dados.
    game_state.record_dice(game_state.DiceResult(
        attacker_rolls=combat.attacker_rolls,
        defender_rolls=combat.defender_rolls,
        attacker_losses=combat.attacker_losses,
        defender_losses=combat.defender_losses,
        conquered=conquered,
    ))

    # Persiste el combate en el historial de batallas (best-effort).
    try:
        user_owner = current_user.get("clan_id") or current_user["id"]
        battle = batallas_repo.create_battle(
            zone_id=zone_id,
            attacker_clan_id=user_owner,
            defender_clan_id=target_owner or "",
            attacker_power=source_armies,
            defender_power=target_armies,
        )
        batallas_repo.update_battle(battle["id"], {
            "result": "attacker_wins" if conquered else "defender_wins",
            "attacker_rolls": combat.attacker_rolls,
            "defender_rolls": combat.defender_rolls,
            "attacker_losses": combat.attacker_losses,
            "defender_losses": combat.defender_losses,
        })
    except Exception as exc:
        logger.warning("battle history save failed (non-critical): %s", exc)

    return {
        "conquered": conquered,
        "attacker_rolls": combat.attacker_rolls,
        "defender_rolls": combat.defender_rolls,
        "attacker_losses": combat.attacker_losses,
        "defender_losses": combat.defender_losses,
        "source_armies_after": max(0, new_source),
        "target_armies_after": new_target,
        "turn_violation": not game_state.is_players_turn(current_user["id"]),
    }


def _sync_location_update(user_id: str, lat: float, lng: float) -> dict:
    """Synchronous Firestore + Shapely zone detection (runs in executor)."""
    zone = zonas_repo.find_zone_containing_point(lat, lng)
    payload: dict = {"event": "location_ack", "lat": lat, "lng": lng}
    if zone:
        payload["zone"] = {
            "id": zone["id"],
            "name": zone["name"],
            "owner_clan_id": zone.get("owner_clan_id"),
        }
    # Publish to Pub/Sub for metrics pipeline. Fire-and-forget: log but
    # never block the WebSocket response on a publish failure.
    try:
        pubsub_publisher.publish_location_event(user_id, lat, lng, zone)
    except Exception as exc:
        logger.warning(f"Pub/Sub location publish failed for {user_id}: {exc}")
    return payload


async def handle_location_update(user_id: str, lat: float, lng: float, manager) -> None:
    """Called from WebSocket endpoint."""
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(None, _sync_location_update, user_id, lat, lng)
    await manager.send_personal_message(payload, user_id)
