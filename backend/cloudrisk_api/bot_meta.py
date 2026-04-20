"""
CloudRISK — Meta y objetivos del juego para bots
=================================================

META PRINCIPAL: Controlar el mayor número de distritos de Valencia.
Más zonas = más armies por turno = más poder = más zonas. Ciclo virtuoso.

CONDICIÓN DE VICTORIA: Jugador con más zonas al acabar (o último en pie).

Orden de prioridades del bot cada turno (de mayor a menor urgencia):
"""

# ── 0. EMERGENCIA DEFENSIVA ──────────────────────────────────────────────────
# Si una zona propia tiene BSR (armies enemigas adyacentes / mis armies) >= UMBRAL,
# refuerza ya — antes de atacar o conquistar. Un flanco abierto te puede costar
# la partida en el siguiente turno del rival.
BSR_CRITICO = 2.5          # ratio que activa refuerzo de emergencia

# ── 1. FORTIFY ARIETE ────────────────────────────────────────────────────────
# SIEMPRE que tengas pool ≥ MIN_POOL_ARIETE, vuelca armies en tu zona fronteriza
# más fuerte ANTES de conquistar. Razón: un ariete fuerte te permite encadenar
# ataques y sobrevivir contraataques. Se reservan 2 armies para una conquista.
MIN_POOL_ARIETE = 3        # pool mínimo para activar el ariete
RESERVA_CONQUISTA = 2      # armies reservados para poder conquistar tras fortify

# ── 2. CONQUISTAR ZONAS LIBRES ───────────────────────────────────────────────
# Prioridad MÁXIMA de expansión: más zonas = más income. Conquista siempre que
# haya zona libre adyacente y tengas pool suficiente.
# Scoring de zona libre = PESO_ENEMIGOS * vecinos_enemigos + PESO_CONEXION * total_vecinos
COSTE_CONQUISTA = 2        # armies del pool que cuesta reclamar una zona libre
PESO_VECINOS_ENEMIGOS = 3.0   # zonas que bloquean expansión rival valen más
PESO_CONECTIVIDAD = 1.0       # zonas más conectadas = más rutas de ataque futuro

# ── 3. ELIMINAR RIVALES DÉBILES ──────────────────────────────────────────────
# Si un rival tiene pocas zonas Y somos adyacentes, remátalo aunque sea en
# igualdad de fuerzas. Sus zonas pasan a ser nuestras = salto de income brutal.
UMBRAL_RIVAL_MORIBUNDO = 4    # zonas por debajo de las que un rival es "presa fácil"

# ── 4-6. ATAQUES ─────────────────────────────────────────────────────────────
# Aplaste (ventaja >= APLASTE_MIN): siempre atacar — gratis, gran valor.
# Ventaja simple (mi_def > su_def): siempre atacar.
# Igualdad (mi_def == su_def): atacar con probabilidad PROB_ATAQUE_IGUAL.
APLASTE_MIN = 2            # diferencia mínima de armies para considerar "aplaste"
PROB_ATAQUE_IGUAL = 0.65   # probabilidad de arriesgar un ataque igualado

# ── 7. FORTIFY SOBRANTE ──────────────────────────────────────────────────────
# Si llega pool sobrante a este punto (raro), gastarlo en el ariete fronterizo.

# ── INCOME POR TURNO ─────────────────────────────────────────────────────────
# pool_nuevo = max(MIN_BONUS, zonas_propias // DIVISOR)
# Ejemplo con MIN_BONUS=6, DIVISOR=2:
#   5 zonas  →  6 armies/turno
#  10 zonas  →  6 armies/turno
#  14 zonas  →  7 armies/turno
#  20 zonas  → 10 armies/turno   ← aquí empieza la bola de nieve
#  30 zonas  → 15 armies/turno
# CONCLUSIÓN: cada zona extra vale más que la anterior. EXPANDIR ES GANAR.
