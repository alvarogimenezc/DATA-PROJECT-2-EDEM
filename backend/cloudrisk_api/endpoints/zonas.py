"""Router: Zone listing, cloudrisk, and real-time location detection."""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)


import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from cloudrisk_api.configuracion import settings
from cloudrisk_api.database import zonas as zonas_repo, clanes as clanes_repo, usuarios as usuarios_repo, publicador_pubsub as pubsub_publisher
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import estado_juego as game_state, dados, adyacencia
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
    # Regla Risk: reclamar un territorio libre requiere ser vecino. Evita que
    # un jugador reclame zonas del otro lado del mapa sin haber expandido
    # hacia allí. El frontend también oculta el botón cuando no hay
    # adyacencia, pero la defensa aquí protege contra llamadas directas.
    user_owner = current_user.get("clan_id") or current_user["id"]
    adj_map = adjacency.get_adjacency()
    neighbors = adj_map.get(zone_id, frozenset())
    if neighbors:
        owns_neighbor = any(
            (z := zonas_repo.get_zone_by_id(nid)) and (z.get("owner_clan_id") == user_owner)
            for nid in neighbors
        )
        if not owns_neighbor:
            raise HTTPException(
                status_code=400,
                detail="No eres adyacente a esta zona libre. Conquista primero un barrio vecino.",
            )
    # Si la zona no tiene entrada en adj_map (caso extremo: zona aislada sin
    # geojson), dejamos pasar para no bloquear partidas — la excepción aquí
    # es peor que la regla suavizada.

    # Regla: reclamar una zona libre cuesta 1 tropa, que se deposita como
    # guarnición. Si el jugador no tiene al menos 1 tropa disponible, no se
    # puede conquistar todavía (debe caminar / pedir refuerzos primero).
    user_power = int(current_user.get("power_points") or 0)
    if user_power < 1:
        raise HTTPException(
            status_code=400,
            detail="Necesitas al menos 1 tropa disponible para conquistar. Camina más para ganar tropas.",
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

    # Post-claim: depositamos 1 tropa en la zona y descontamos 1 del pool del
    # jugador. No son estrictamente atómicos con el conquer, pero la ventana
    # es mínima y en el peor caso (desconexión entre las dos writes) quedas
    # con la zona a 0 defensas — escenario benigno: siempre puedes Desplegar
    # luego para reforzarla.
    try:
        zonas_repo.update_zone(zone_id, {"defense_level": 1})
    except Exception:
        pass
    try:
        usuarios_repo.update_user(current_user["id"], {"power_points": user_power - 1})
    except Exception:
        pass

    return {
        "message": f"Zone '{zone['name']}' conquered! +1 tropa desplegada.",
        "zone_id": zone_id,
        "new_defense": 1,
        "armies_spent": 1,
        "armies_remaining": max(0, user_power - 1),
    }


class AttackRequest(BaseModel):
    from_zone_id: str
    attacker_dice: int   # 1, 2, or 3


@router.post("/{zone_id}/attack")
def attack_zone(zone_id: str, req: AttackRequest, current_user: dict = Depends(get_current_user)):
    """Attack a contested zone with Risk dice rules.

    Turn check (soft): if it's not the caller's turn the response still
    resolves combat so solo-play doesn't dead-lock, but the response
    includes turn_violation=True so the UI can nag the user.
    """
    # Validate inputs
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

    # Risk rule: el objetivo debe ser adyacente (compartir frontera) a la
    # zona de origen. Si el grafo no contiene la zona (caso extremo: zona
    # sin geojson) lo dejamos pasar para no dead-lockar partidas, pero el
    # caso normal es que ambos ids existan en el grafo precomputado.
    adj_map = adjacency.get_adjacency()
    if req.from_zone_id in adj_map:
        if zone_id not in adj_map[req.from_zone_id]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Target zone is not adjacent to source. "
                    f"You can only attack neighboring territories."
                ),
            )

    source_armies = int(source.get("defense_level") or 0)
    target_armies = int(target.get("defense_level") or 0)
    # Attacker must leave 1 army behind → needs strictly more than dice count.
    if source_armies <= req.attacker_dice:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {req.attacker_dice + 1} armies in source (have {source_armies})",
        )

    # Defender dice: 2 requires >=2 armies, else 1. Free zones with 0 defense
    # surrender instantly (no roll, no losses). We still apply the updates
    # atomically so a parallel attack on the same target can't double-grant.
    if target_armies == 0:
        committed = zonas_repo.resolve_combat_atomic(
            source_id=req.from_zone_id,
            target_id=zone_id,
            attacker_clan=current_user["id"],
            expected_source_armies=source_armies,
            expected_target_owner=target_owner,
            expected_target_armies=0,
            new_source_armies=source_armies - req.attacker_dice,
            new_target_armies=req.attacker_dice,
            conquered=True,
            conquered_at=datetime.utcnow().isoformat(),
        )
        if not committed:
            raise HTTPException(status_code=409, detail="Zone state changed during combat; retry")
        return {
            "conquered": True,
            "attacker_rolls": [], "defender_rolls": [],
            "attacker_losses": 0, "defender_losses": 0,
            "source_armies_after": source_armies - req.attacker_dice,
            "target_armies_after": req.attacker_dice,
            "turn_violation": not game_state.is_players_turn(current_user["id"]),
        }

    defender_dice = 2 if target_armies >= 2 else 1
    combat = dice.resolve(req.attacker_dice, defender_dice)

    new_source = source_armies - combat.attacker_losses
    new_target = target_armies - combat.defender_losses
    conquered = new_target <= 0

    if conquered:
        moved = max(req.attacker_dice, 1)   # must move in >= dice rolled
        new_source -= moved
        new_target = moved

    # Single atomic update of BOTH zones. Optimistic concurrency: if either
    # zone's state changed between our earlier read and now, the transaction
    # fails with 409 and the client can retry.
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

    # Cache for frontend dice animation.
    result = game_state.DiceResult(
        attacker_rolls=combat.attacker_rolls,
        defender_rolls=combat.defender_rolls,
        attacker_losses=combat.attacker_losses,
        defender_losses=combat.defender_losses,
        conquered=conquered,
    )
    game_state.record_dice(result)

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
