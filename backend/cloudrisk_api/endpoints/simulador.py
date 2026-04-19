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


router = APIRouter(prefix="/simulate_bots", tags=["simulation"])


class SimulateBotsRequest(BaseModel):
    actions_per_bot_turn: int = Field(
        default=3, ge=1, le=10,
        description="Acciones que ejecuta cada bot en su turno (1-10). Default 3.",
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


def _get_leader(zones: list[dict], exclude_bot_id: str) -> str | None:
    """Jugador con más zonas (excluyendo al bot que está pensando). Empate →
    aleatorio. Así los bots van a por el que va ganando en lugar de picotear
    al primero que les pille a mano."""
    counts: dict[str, int] = {}
    for z in zones:
        owner = z.get("owner_clan_id")
        if owner and owner != exclude_bot_id:
            counts[owner] = counts.get(owner, 0) + 1
    if not counts:
        return None
    top = max(counts.values())
    tied = [pid for pid, c in counts.items() if c == top]
    return random.choice(tied)


def _choose_action(
    bot_id: str, zones: list[dict], pool: int
) -> tuple[str, dict | None, dict | None]:
    """Devuelve (tipo, zona_objetivo, zona_origen).
    `zona_origen` sólo aplica a 'attack' — es la zona mía desde la que ataco
    (necesito defense>=2 ahí para que una quede tomando la conquistada).

    Prioridad (de arriba abajo — lo primero que encaja gana):
      1. Atacar zona del LÍDER, adyacente a una mía, con ventaja
         (mi_def > su_def). Si hay varias, la más débil primero.
      2. Atacar a cualquier enemigo débil (def<=2) adyacente y con ventaja.
      3. Conquistar zona libre ADYACENTE a las mías (cuesta INITIAL_ARMIES
         del pool — si no llego, me salto el paso).
      4. Fortificar frontera (zona mía con vecino enemigo, la más débil
         primero — taponamos huecos antes de inflar la zona más segura).
      5. idle — todo lo demás."""
    by_id = {z["id"]: z for z in zones}
    mine = [z for z in zones if z.get("owner_clan_id") == bot_id]

    # Pares (enemigo_atacable, mi_origen) — sólo si mi origen tiene >=2 defense.
    attackable: list[tuple[dict, dict]] = []
    for m in mine:
        if int(m.get("defense_level") or 0) < 2:
            continue
        for nid in neighbors_of(m["id"]):
            n = by_id.get(nid)
            if n and n.get("owner_clan_id") and n.get("owner_clan_id") != bot_id:
                attackable.append((n, m))

    # 1. Al líder con ventaja
    leader_id = _get_leader(zones, bot_id)
    if leader_id and attackable:
        advantage = [
            (t, o) for t, o in attackable
            if t.get("owner_clan_id") == leader_id
            and int(o.get("defense_level") or 0) > int(t.get("defense_level") or 0)
        ]
        if advantage:
            advantage.sort(key=lambda p: int(p[0].get("defense_level") or 0))
            t, o = advantage[0]
            return "attack", t, o

    # 2. Enemigo débil cualquiera con ventaja
    easy = [
        (t, o) for t, o in attackable
        if int(o.get("defense_level") or 0) > int(t.get("defense_level") or 0)
        and int(t.get("defense_level") or 0) <= 2
    ]
    if easy:
        easy.sort(key=lambda p: int(p[0].get("defense_level") or 0))
        t, o = easy[0]
        return "attack", t, o

    # 3. Conquistar libre adyacente (si hay pool)
    if pool >= settings.INITIAL_ARMIES_PER_ZONE:
        free_adjacent: list[dict] = []
        for m in mine:
            for nid in neighbors_of(m["id"]):
                n = by_id.get(nid)
                if n and not n.get("owner_clan_id"):
                    free_adjacent.append(n)
        if free_adjacent:
            return "conquer", random.choice(free_adjacent), None
        # Sin libre adyacente — caso raro, pero por si acaso tomamos una
        # aislada (no debería bloquear el turno).
        any_free = [z for z in zones if not z.get("owner_clan_id")]
        if any_free:
            return "conquer", random.choice(any_free), None

    # 4. Fortificar frontera
    if pool >= 1:
        frontier: list[dict] = []
        for m in mine:
            if int(m.get("defense_level") or 0) >= MAX_ZONE_DEFENSE:
                continue
            has_enemy = any(
                (by_id.get(nid) and by_id[nid].get("owner_clan_id")
                 and by_id[nid].get("owner_clan_id") != bot_id)
                for nid in neighbors_of(m["id"])
            )
            if has_enemy:
                frontier.append(m)
        if frontier:
            frontier.sort(key=lambda z: int(z.get("defense_level") or 0))
            return "fortify", frontier[0], None
        # Sin frontera (aislado o todo interior) → cualquiera bajo cap.
        under = [z for z in mine if int(z.get("defense_level") or 0) < MAX_ZONE_DEFENSE]
        if under:
            return "fortify", random.choice(under), None

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
                "new_defense": 1}

    if action == "fortify":
        bot = usuarios_repo.get_user_by_id(bot_id) or {}
        prev_pool = int(bot.get("power_points") or 0)
        if prev_pool < 1:
            return {"bot": bot_id, "action": "idle", "reason": "low_pool"}
        prev_def = int(zone.get("defense_level") or 0)
        new_def = min(MAX_ZONE_DEFENSE, prev_def + 1)
        if new_def == prev_def:
            return {"bot": bot_id, "action": "idle", "reason": "max_def"}
        usuarios_repo.update_user(bot_id, {"power_points": prev_pool - 1})
        zonas_repo.update_zone(zone["id"], {"defense_level": new_def})
        return {"bot": bot_id, "action": "fortify", "zone_id": zone["id"],
                "zone_name": zone.get("name"),
                "prev_defense": prev_def, "new_defense": new_def,
                "pool_left": prev_pool - 1}

    return {"bot": bot_id, "action": "idle"}


def _run_bot_turn(bot_id: str, actions_count: int, now_iso: str) -> list[dict]:
    """Ejecuta `actions_count` acciones para un bot. Relee zonas Y pool entre
    cada acción: así el bot no se pisa (p. ej. conquistar dos veces la misma
    libre) y tampoco gasta más pool del que tiene."""
    out: list[dict] = []
    for _ in range(actions_count):
        zones = zonas_repo.list_zones()
        bot = usuarios_repo.get_user_by_id(bot_id) or {}
        pool = int(bot.get("power_points") or 0)
        kind, zone, origin = _choose_action(bot_id, zones, pool)
        if zone is None:
            out.append({"bot": bot_id, "action": "idle"})
            continue
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
