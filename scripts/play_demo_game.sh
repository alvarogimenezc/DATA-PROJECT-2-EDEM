#!/usr/bin/env bash
# play_demo_game.sh — Crea una partida rápida en la API para tener datos que mostrar.
#
# Pasos:
#   1. Hace login con los 4 jugadores base.
#   2. Registra 2 jugadores nuevos (Centro y Costa).
#   3. Suma 10,000 pasos a todos para que tengan tropas.
#   4. Crea clanes ("Pink Lions" y "Cyan Wolves") y une a los jugadores.
#   5. Conquista zonas por Valencia.

set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
PASS="demo1234"

c_section() { printf "\n\033[1;36m▸ %s\033[0m\n" "$1"; }
c_ok()      { printf "  \033[32mok\033[0m  %s\n" "$1"; }
c_warn()    { printf "  \033[33m??\033[0m  %s\n" "$1"; }

j() { python -c "import sys,json; print(json.load(sys.stdin)$1)"; }

login() {
  curl -sf -X POST "$API/api/v1/users/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$1&password=$PASS" | j "['access_token']"
}

register() {
  # name, email
  curl -sf -X POST "$API/api/v1/users/register" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$1\",\"email\":\"$2\",\"password\":\"$PASS\"}" | j "['access_token']" 2>/dev/null \
    || login "$2"   
}

with_token() { curl -sf -H "Authorization: Bearer $1" "${@:2}"; }

c_section "1. Login the 4 seeded players"
T_NORTE=$(login norte@cloudrisk.app);  c_ok "norte"
T_SUR=$(login sur@cloudrisk.app);      c_ok "sur"
T_ESTE=$(login este@cloudrisk.app);    c_ok "este"
T_OESTE=$(login oeste@cloudrisk.app);  c_ok "oeste"

c_section "2. Register 2 extra commanders"
T_CENTRO=$(register "Comandante Centro" centro@cloudrisk.app); c_ok "centro"
T_COSTA=$(register "Comandante Costa"   costa@cloudrisk.app);  c_ok "costa"

c_section "3. Sync 10 000 steps per player (→ ~100 power points each)"
for tok in $T_NORTE $T_SUR $T_ESTE $T_OESTE $T_CENTRO $T_COSTA; do
  with_token "$tok" -X POST "$API/api/v1/steps/sync" \
    -H "Content-Type: application/json" -d '{"steps":10000}' >/dev/null && c_ok "+10000 steps"
done

c_section "4. Form clans"
CLAN_PINK=$(curl -sf -X POST "$API/api/v1/clans/" \
  -H "Authorization: Bearer $T_NORTE" -H "Content-Type: application/json" \
  -d '{"name":"Pink Lions","color":"#ff2d92"}' | j "['id']")
c_ok "Pink Lions ($CLAN_PINK) — leader: norte"

CLAN_CYAN=$(curl -sf -X POST "$API/api/v1/clans/" \
  -H "Authorization: Bearer $T_SUR" -H "Content-Type: application/json" \
  -d '{"name":"Cyan Wolves","color":"#00f0ff"}' | j "['id']")
c_ok "Cyan Wolves ($CLAN_CYAN) — leader: sur"

with_token "$T_ESTE"   -X POST "$API/api/v1/clans/$CLAN_PINK/join" >/dev/null && c_ok "este → Pink Lions"
with_token "$T_CENTRO" -X POST "$API/api/v1/clans/$CLAN_PINK/join" >/dev/null && c_ok "centro → Pink Lions"
with_token "$T_OESTE"  -X POST "$API/api/v1/clans/$CLAN_CYAN/join" >/dev/null && c_ok "oeste → Cyan Wolves"
with_token "$T_COSTA"  -X POST "$API/api/v1/clans/$CLAN_CYAN/join" >/dev/null && c_ok "costa → Cyan Wolves"

c_section "5. Conquer + deploy armies"

deploy() {
  local tok=$1 zone=$2 amount=$3 who=$4
  curl -sf -X POST "$API/api/v1/zones/$zone/conquer" -H "Authorization: Bearer $tok" >/dev/null 2>&1 || true
  if curl -sf -X POST "$API/api/v1/armies/place" \
       -H "Authorization: Bearer $tok" -H "Content-Type: application/json" \
       -d "{\"location_id\":\"$zone\",\"amount\":$amount}" >/dev/null; then
    c_ok "$who → $zone (+$amount armies)"
  else
    c_warn "$who → $zone failed (probably not enough power)"
  fi
}

deploy "$T_NORTE"  "zona-borbot"        15 "norte"
deploy "$T_NORTE"  "zona-poble-nou"      8 "norte"
deploy "$T_ESTE"   "zona-la-malva-rosa" 12 "este"
deploy "$T_ESTE"   "zona-benimaclet"     6 "este"
deploy "$T_CENTRO" "zona-el-carme"      18 "centro"
deploy "$T_CENTRO" "zona-russafa"       10 "centro"

deploy "$T_SUR"   "zona-pinedo"         20 "sur"
deploy "$T_SUR"   "zona-la-punta"        9 "sur"
deploy "$T_OESTE" "zona-mestalla"  14 "oeste"   # avoid Unicode in bash heredoc
deploy "$T_OESTE" "zona-vara-de-quart"   7 "oeste"
deploy "$T_COSTA" "zona-natzaret"       16 "costa"
deploy "$T_COSTA" "zona-el-grau"        11 "costa"

c_section "6. Final state"
curl -s "$API/api/v1/zones/" | python -c "
import sys, json
zones = json.load(sys.stdin)
owned = [z for z in zones if z.get('owner_clan_id')]
print(f'  Total zones: {len(zones)}')
print(f'  Conquered:   {len(owned)}')
print(f'  Free:        {len(zones) - len(owned)}')
print()
clans = {}
for z in owned:
    cid = z['owner_clan_id']
    clans.setdefault(cid, []).append((z['name'], z.get('defense_level', 0)))
for cid, items in clans.items():
    total_def = sum(d for _, d in items)
    print(f'  Clan {cid[:8]}...  {len(items)} zones, {total_def} total armies')
    for name, defense in sorted(items, key=lambda x: -x[1]):
        bar = '#' * min(defense, 30)
        print(f'    {name:28s} {defense:3d}  {bar}'.encode('ascii', 'replace').decode())"
