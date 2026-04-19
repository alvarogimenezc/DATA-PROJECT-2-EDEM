"""
Endpoint de simulación de bots disparado desde el frontend.

Se distingue del script `backend/simulador_bots.py`:
  - `simulador_bots.py` es un cliente HTTP que habla con la API como un
    jugador externo — ideal para stress tests y smoke tests en CI.
  - Este módulo se ejecuta DENTRO del backend, toca los repos directos
    (zonas_repo, usuarios_repo) y aplica cambios visibles al instante en
    el mapa del frontend. Es el botón "Simular bots" del lobby.

Modelo de juego (v3.2 — turnos respetados):

  1. El usuario juega su turno y pulsa "Terminar turno".
  2. El frontend llama a `/simulate_bots/run`.
  3. Este endpoint bucle: mientras `current_player_id` sea un bot,
     ejecuta una tanda de `actions_per_bot_turn` acciones para ese bot
     y avanza el turno. Así pasan 1, 2 o 3 bots hasta que vuelve el
     turno del usuario.
  4. Si ya es turno del usuario al llamar → no hace nada (no-op).

Acciones de cada bot (v3.3 — IA más cabrona y paga su pool):
  1. Atacar al LÍDER (jugador con más zonas) si tiene una zona suya adyacente
     a una mía con ventaja (mi defense > su defense). No va a ciegas.
  2. Atacar a cualquier enemigo débil adyacente con ventaja clara.
  3. Conquistar una zona libre ADYACENTE a las mías (pool >= 2).
  4. Fortificar una zona fronteriza propia (la más débil primero, pool >= 1).

Cambios importantes vs v3.2:
  - Antes los bots creaban tropas de la NADA (conquer/fortify no tocaban pool).
    Ahora pagan igual que el humano: 2 por conquer, 1 por fortify. Y reciben
    el mismo refuerzo de turno (_grant_turn_bonus) cuando acaban su tanda.
  - Antes conquistaban zonas random por todo el mapa (sin adyacencia). Ahora
    sólo zonas libres PEGADAS a las suyas — crecimiento contiguo como en Risk.
  - Los ataques ahora exigen zona origen con defense >= 2 (una queda tomando
    la conquistada, otra se queda defendiendo el origen).
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cloudrisk_api.configuracion import settings, MAX_ZONE_DEFENSE
from cloudrisk_api.database import zonas as zonas_repo, usuarios as usuarios_repo
from cloudrisk_api.services.autenticacion import get_current_user
from cloudrisk_api.services import estado_juego as game_state
from cloudrisk_api.services.adyacencia import neighbors_of
from cloudrisk_api.endpoints.turno import _grant_turn_bonus
from cloudrisk_api.bot_meta import (
    BSR_CRITICO, MIN_POOL_ARIETE, RESERVA_CONQUISTA,
    PESO_VECINOS_ENEMIGOS, PESO_CONECTIVIDAD,
    UMBRAL_RIVAL_MORIBUNDO, APLASTE_MIN, PROB_ATAQUE_IGUAL,
)


router = APIRouter(prefix="/simulate_bots", tags=["simulation"])


class SimulateBotsRequest(BaseModel):
    actions_per_bot_turn: int = Field(
        default=15, ge=1, le=30,
        description="Acciones máximas por turno de bot (para en idle). Default 15.",
    )
    # "loop"  → default histórico: juega bots hasta que vuelva mi turno en UNA
    #           sola llamada HTTP. Útil para scripts o para saltarse bots rápido.
    # "step"  → juega UN solo turno de bot y devuelve. El frontend encadena
    #           varias llamadas con pausa para que se vea el TurnBanner
    #           cambiando y el mapa refrescándose entre bot y bot.
    mode: Literal["loop", "step"] = Field(
        default="loop",
        description="'loop' = todos los bots de golpe; 'step' = un turno y vuelve.",
    )


def _zone_counts(zones: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for z in zones:
        o = z.get("owner_clan_id")
        if o:
            counts[o] = counts.get(o, 0) + 1
    return counts


def _bsr(zone: dict, by_id: dict, bot_id: str) -> float:
    """Border Security Ratio: armies enemigas adyacentes / mis armies.
    BSR >= BSR_CRITICO → amenaza urgente, fortifica antes de atacar.
    """
    my_def = max(int(zone.get("defense_level") or 1), 1)
    enemy_sum = sum(
        int(by_id[nid].get("defense_level") or 0)
        for nid in neighbors_of(zone["id"])
        if by_id.get(nid) and by_id[nid].get("owner_clan_id")
        and by_id[nid].get("owner_clan_id") != bot_id
    )
    return enemy_sum / my_def


def _free_zone_score(zone: dict, by_id: dict, bot_id: str) -> float:
    """Puntuación estratégica de una zona libre a conquistar.
    Prioriza chokepoints (bloquean expansión rival) y zonas conectadas.
    """
    enemy_nb = sum(
        1 for nid in neighbors_of(zone["id"])
        if by_id.get(nid) and by_id[nid].get("owner_clan_id")
        and by_id[nid].get("owner_clan_id") != bot_id
    )
    total_nb = len(list(neighbors_of(zone["id"])))
    return enemy_nb * PESO_VECINOS_ENEMIGOS + total_nb * PESO_CONECTIVIDAD


def _best_attack(attackable: list[tuple[dict, dict]]) -> tuple[dict, dict]:
    """Target más débil primero; en empate, origin más fuerte (encadenamiento)."""
    attackable.sort(key=lambda p: (
        int(p[0].get("defense_level") or 0),
        -int(p[1].get("defense_level") or 0),
    ))
    return attackable[0]


def _frontier_ariete(mine: list[dict], by_id: dict, bot_id: str) -> dict | None:
    """Zona fronteriza más fuerte — el ariete donde concentramos armies."""
    frontier = [
        m for m in mine
        if any(
            by_id.get(nid) and by_id[nid].get("owner_clan_id")
            and by_id[nid].get("owner_clan_id") != bot_id
            for nid in neighbors_of(m["id"])
        )
    ]
    if frontier:
        return max(frontier, key=lambda z: int(z.get("defense_level") or 0))
    return max(mine, key=lambda z: int(z.get("defense_level") or 0)) if mine else None


def _choose_action(
    bot_id: str, zones: list[dict], pool: int
) -> tuple[str, dict | None, dict | None]:
    """IA v5.0 — meta clara: máximo territorio, fronteras fuertes.

    Ver bot_meta.py para la explicación completa de cada prioridad.

    Prioridades:
      0. Emergencia BSR ≥ 2.5 → fortify urgente
      1. Fortify ariete si pool ≥ 3 (ANTES de conquistar, reserva 2 para conquista)
      2. Conquistar zona libre adyacente (expansión — prioridad máxima de income)
      3. Eliminar rival moribundo (≤ 4 zonas)
      4. Aplaste al líder (ventaja ≥ 2)
      5. Aplaste a cualquier rival (ventaja ≥ 2)
      6. Ventaja simple
      7. Ataque igualado (65%)
      8. Fortify sobrante
      9. idle
    """
    by_id = {z["id"]: z for z in zones}
    mine = [z for z in zones if z.get("owner_clan_id") == bot_id]
    if not mine:
        return "idle", None, None

    counts = _zone_counts(zones)

    # ── 0. EMERGENCIA BSR ─────────────────────────────────────────────────
    if pool >= 1:
        critical = [m for m in mine if _bsr(m, by_id, bot_id) >= BSR_CRITICO]
        if critical:
            critical.sort(key=lambda z: _bsr(z, by_id, bot_id), reverse=True)
            return "fortify", critical[0], None

    # ── 1. FORTIFY ARIETE (antes de conquistar, reservando 2 para conquista) ─
    if pool >= MIN_POOL_ARIETE:
        ariete = _frontier_ariete(mine, by_id, bot_id)
        if ariete:
            return "fortify", ariete, None

    # ── 2. CONQUISTAR ZONA LIBRE ADYACENTE ────────────────────────────────
    if pool >= settings.INITIAL_ARMIES_PER_ZONE:
        seen: set[str] = set()
        free_adj: list[dict] = []
        for m in mine:
            for nid in neighbors_of(m["id"]):
                n = by_id.get(nid)
                if n and not n.get("owner_clan_id") and n["id"] not in seen:
                    seen.add(n["id"])
                    free_adj.append(n)
        if free_adj:
            free_adj.sort(key=lambda z: _free_zone_score(z, by_id, bot_id), reverse=True)
            return "conquer", free_adj[0], None

    # Pares atacables — origin necesita ≥ 2 defense
    attackable: list[tuple[dict, dict]] = []
    for m in mine:
        if int(m.get("defense_level") or 0) < 2:
            continue
        for nid in neighbors_of(m["id"]):
            n = by_id.get(nid)
            if n and n.get("owner_clan_id") and n.get("owner_clan_id") != bot_id:
                attackable.append((n, m))

    others = {pid: cnt for pid, cnt in counts.items() if pid != bot_id}
    leader_id = max(others, key=others.get) if others else None

    # ── 3. ELIMINACIÓN (rival moribundo) ──────────────────────────────────
    dying = {pid for pid, cnt in counts.items() if pid != bot_id and cnt <= UMBRAL_RIVAL_MORIBUNDO}
    if dying and attackable:
        elim = [
            (t, o) for t, o in attackable
            if t.get("owner_clan_id") in dying
            and int(o.get("defense_level") or 0) >= int(t.get("defense_level") or 0)
        ]
        if elim:
            t, o = _best_attack(elim)
            return "attack", t, o

    # ── 4. APLASTE AL LÍDER ───────────────────────────────────────────────
    if leader_id and attackable:
        crush_ldr = [
            (t, o) for t, o in attackable
            if t.get("owner_clan_id") == leader_id
            and int(o.get("defense_level") or 0) >= int(t.get("defense_level") or 0) + APLASTE_MIN
        ]
        if crush_ldr:
            t, o = _best_attack(crush_ldr)
            return "attack", t, o

    # ── 5. APLASTE A CUALQUIERA ───────────────────────────────────────────
    crush_any = [
        (t, o) for t, o in attackable
        if int(o.get("defense_level") or 0) >= int(t.get("defense_level") or 0) + APLASTE_MIN
    ]
    if crush_any:
        t, o = _best_attack(crush_any)
        return "attack", t, o

    # ── 6. VENTAJA SIMPLE ─────────────────────────────────────────────────
    with_adv = [
        (t, o) for t, o in attackable
        if int(o.get("defense_level") or 0) > int(t.get("defense_level") or 0)
    ]
    if with_adv:
        t, o = _best_attack(with_adv)
        return "attack", t, o

    # ── 7. ATAQUE IGUALADO ────────────────────────────────────────────────
    equal = [
        (t, o) for t, o in attackable
        if int(o.get("defense_level") or 0) == int(t.get("defense_level") or 0)
    ]
    if equal and random.random() < PROB_ATAQUE_IGUAL:
        t, o = _best_attack(equal)
        return "attack", t, o

    # ── 8. FORTIFY SOBRANTE ───────────────────────────────────────────────
    if pool >= 1:
        ariete = _frontier_ariete(mine, by_id, bot_id)
        if ariete:
            return "fortify", ariete, None

    return "idle", None, None


def _apply_action(
    bot_id: str, action: str, zone: dict, origin: dict | None, now_iso: str,
) -> dict:
    """Igual que antes pero DEBITA el pool del bot. Antes creaba tropas de la
    nada y el humano jugaba en desventaja — ahora conquer cuesta 2 y fortify 1,
    como al humano. Si el pool no llega, devolvemos idle con razón."""
    if action == "conquer":
        bot = usuarios_repo.get_user_by_id(bot_id) or {}
        prev_pool = int(bot.get("power_points") or 0)
        cost = settings.INITIAL_ARMIES_PER_ZONE
        if prev_pool < cost:
            return {"bot": bot_id, "action": "idle", "reason": "low_pool"}
        usuarios_repo.update_user(bot_id, {"power_points": prev_pool - cost})
        zonas_repo.update_zone(zone["id"], {
            "owner_clan_id": bot_id,
            "defense_level": cost,
            "conquered_at": now_iso,
        })
        return {"bot": bot_id, "action": "conquer", "zone_id": zone["id"],
                "zone_name": zone.get("name"), "new_defense": cost,
                "pool_left": prev_pool - cost}

    if action == "attack":
        # Sin dados — batalla simplificada. El origen pierde 1 (tropa que toma
        # la zona), el target cambia de dueño con defense=1. Mantiene el
        # comportamiento histórico para no romper el resto del juego.
        if origin is not None:
            orig_def = int(origin.get("defense_level") or 0)
            zonas_repo.update_zone(origin["id"], {"defense_level": max(1, orig_def - 1)})
        zonas_repo.update_zone(zone["id"], {
            "owner_clan_id": bot_id,
            "defense_level": 1,
            "conquered_at": now_iso,
        })
        return {"bot": bot_id, "action": "attack", "zone_id": zone["id"],
                "zone_name": zone.get("name"), "prev_owner": zone.get("owner_clan_id"),
                "from_zone": origin["id"] if origin else None,
                "from_zone_name": origin.get("name") if origin else None,
                "new_defense": 1}

    if action == "fortify":
        bot = usuarios_repo.get_user_by_id(bot_id) or {}
        prev_pool = int(bot.get("power_points") or 0)
        if prev_pool < 1:
            return {"bot": bot_id, "action": "idle", "reason": "low_pool"}
        prev_def = int(zone.get("defense_level") or 0)
        # Reserva 2 armies para poder conquistar una zona libre después.
        # Si pool <= 2, gasta todo (ya no puede conquistar de todas formas).
        spend = (prev_pool - RESERVA_CONQUISTA) if prev_pool > RESERVA_CONQUISTA else prev_pool
        spend = max(spend, 1)
        new_def = prev_def + spend
        new_pool = prev_pool - spend
        usuarios_repo.update_user(bot_id, {"power_points": new_pool})
        zonas_repo.update_zone(zone["id"], {"defense_level": new_def})
        return {"bot": bot_id, "action": "fortify", "zone_id": zone["id"],
                "zone_name": zone.get("name"),
                "prev_defense": prev_def, "new_defense": new_def,
                "pool_left": new_pool}

    return {"bot": bot_id, "action": "idle"}


def _run_bot_turn(bot_id: str, actions_count: int, now_iso: str) -> list[dict]:
    """Ejecuta hasta `actions_count` acciones para un bot.

    Para en el primer idle: el bot decide cuántas usar según el estado
    del juego (pool, zonas libres, enemigos adyacentes). Relee zonas y
    pool en cada iteración para no pisar sus propias acciones anteriores.
    """
    out: list[dict] = []
    for _ in range(actions_count):
        zones = zonas_repo.list_zones()
        bot = usuarios_repo.get_user_by_id(bot_id) or {}
        pool = int(bot.get("power_points") or 0)
        kind, zone, origin = _choose_action(bot_id, zones, pool)
        if zone is None:
            break  # nada útil que hacer — el bot termina antes del límite
        out.append(_apply_action(bot_id, kind, zone, origin, now_iso))
    return out


@router.post("/run")
def run_simulation(
    req: SimulateBotsRequest = SimulateBotsRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Avanza los turnos de bots hasta que vuelva a ser turno del usuario.

    Uso típico: el usuario termina su turno en el frontend, el cliente llama
    a este endpoint, y los 1-3 bots intermedios juegan cada uno su turno
    (acciones + end_turn) antes de devolver el control. Si al llamar ya es
    turno del usuario, devuelve `{status: "not_your_turn_expected"}` sin
    hacer nada — el frontend no debe bloquear.

    Límite de seguridad: máximo 4 iteraciones (un ciclo completo de turnos)
    por si algo va mal y el turno nunca vuelve al usuario.
    """
    me = current_user["id"]
    if me not in game_state.DEFAULT_PLAYER_ORDER:
        raise HTTPException(status_code=400, detail="User is not in the lobby order")

    now_iso = datetime.now(timezone.utc).isoformat()
    state = game_state.current()

    if state.current_player_id == me:
        return {
            "status": "noop",
            "reason": "It's already your turn — end it before simulating bots.",
            "current_player_id": me,
            "turns_played": [],
        }

    turns_played: list[dict] = []
    safety_cap = len(game_state.DEFAULT_PLAYER_ORDER)  # 4
    while safety_cap > 0:
        state = game_state.current()
        if state.current_player_id == me:
            break
        bot_id = state.current_player_id
        actions = _run_bot_turn(bot_id, req.actions_per_bot_turn, now_iso)
        summary = {"conquer": 0, "attack": 0, "fortify": 0, "idle": 0}
        for a in actions:
            summary[a["action"]] = summary.get(a["action"], 0) + 1
        # Mismo refuerzo que recibe el humano al terminar su turno — max(3,
        # zonas/3) al pool. Antes los bots no recibían nada y acababan secos
        # tras las primeras conquistas.
        bonus_info = _grant_turn_bonus(bot_id)
        game_state.end_turn()
        turns_played.append({
            "bot": bot_id,
            "turn_number_before": state.turn_number,
            "actions": actions,
            "summary": summary,
            "turn_bonus": bonus_info,
        })
        safety_cap -= 1
        # Modo "step": rompe tras UN turno de bot. El frontend decide cuándo
        # seguir para que se vea el TurnBanner cambiar entre llamadas.
        if req.mode == "step":
            break

    final_state = game_state.current()
    return {
        "status": "ok",
        "triggered_by": me,
        "turns_played_count": len(turns_played),
        "turns_played": turns_played,
        "current_player_id": final_state.current_player_id,
        "turn_number": final_state.turn_number,
        "phase": final_state.phase,
    }
