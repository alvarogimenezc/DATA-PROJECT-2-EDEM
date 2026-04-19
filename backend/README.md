# Backend — CloudRISK API

Servicio FastAPI que da soporte al juego. Tres capas:

```
HTTP / WebSocket
       │
   ┌───▼─────────────┐    ┌─────────────┐    ┌──────────────────┐
   │ routers/        │ →  │ services/   │ →  │ repositories/    │
   │  (rutas HTTP)   │    │ (auth, IA,  │    │ (acceso a datos) │
   │                 │    │   websocket)│    │  ↓               │
   │                 │    │             │    │  almacen_en_memoria │
   │                 │    │             │    │  O Firestore     │
   └─────────────────┘    └─────────────┘    └──────────────────┘
```

## Arranque rápido

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # o .venv/bin/activate
pip install -r requirements.txt

export USE_LOCAL_STORE=1          # modo en memoria, no necesita credenciales GCP
export SECRET_KEY=dev-secret-key
python -m uvicorn cloudrisk_api.main:app --reload --port 8080
```

Abre http://localhost:8080/api/v1/docs para ver el Swagger UI.
Ejecuta `pytest` para correr la suite de tests (actualmente **7 passed, 1 xfailed**).

## Mapa de ficheros — cada archivo y qué hace

### Nivel superior

| Archivo | Rol |
|---|---|
| **`cloudrisk_api/main.py`** | Punto de entrada de la app. Construye la app FastAPI, monta todos los routers bajo `/api/v1`, define la sonda `/health`, define el endpoint WebSocket `/ws/{user_id}` y ejecuta `seed_zones()` + `seed_demo_players()` al arrancar cuando `USE_LOCAL_STORE=1`. |
| **`cloudrisk_api/configuracion.py`** | Clase pydantic-settings que lee variables de entorno: `PROJECT_ID`, `SECRET_KEY`, nombres de colecciones Firestore, dataset/tablas BigQuery, parámetros del juego (`POWER_PER_STEPS`, `BATTLE_DURATION_HOURS`, `CLOUDRISK_MIN_MEMBERS`). |

### `routers/` — manejadores de rutas HTTP (cada endpoint vive aquí)

Cada archivo posee un recurso y exporta un `router = APIRouter(prefix="/<recurso>")`. `main.py` los monta todos bajo `/api/v1`.

| Archivo | Endpoints | Propósito |
|---|---|---|
| **`usuarios.py`** | `POST /users/register`, `POST /users/login`, `GET /users/me` | Creación de cuenta, login con password, lectura de perfil protegida por JWT. |
| **`clanes.py`** | `POST /clans/`, `GET /clans/`, `POST /clans/leave`, `POST /clans/{id}/join`, `POST /clans/{id}/delete` | Formar un clan, unirse a uno, salir de uno. Conquistar zonas requiere un clan. |
| **`zonas.py`** | `GET /zones/`, `GET /zones/adjacency`, `GET /zones/{id}`, `POST /zones/{id}/conquer`, `POST /zones/{id}/attack` + helper WebSocket `handle_location_update()` | Los 87 barrios de Valencia + grafo de adyacencia + combate Risk dice. El helper WS se invoca desde `main.py` cada vez que el frontend envía un evento `location_update`. |
| **`batallas.py`** ⚠️ `deprecated=True` | `POST /battles/`, `GET /battles/`, `GET /battles/{id}`, `GET /battles/{id}/advice`, `POST /battles/{id}/resolve`, `POST /battles/resolve-expired` | Sistema de combate antiguo (power + d6). Se mantiene sólo para histórico y la resolución programada vía Cloud Scheduler. El sistema canónico es `/zones/{id}/attack` (dados Risk). |
| **`pasos.py`** | `POST /steps/sync`, `GET /steps/history`, `GET /steps/realtime-ingestion-status` + helper WS `handle_step_update()` | Los pasos reales sincronizados con el topic `player-movements`. El *scoring* ya no se hace aquí — lo aplica el pipeline Dataflow `cloudrisk_unified`. |
| **`ejercitos.py`** | `GET /armies/balance`, `POST /armies/place`, `GET /armies/locations`, `POST /armies/fortify` | Desplegar / mover tropas entre zonas propias. `fortify` respeta la invariante `MIN_GARRISON` (no deja la origen por debajo de 2). |
| **`turno.py`** | `POST /turn/setup` (🔒 header `X-Scheduler-Token`), `GET /turn/`, `POST /turn/advance`, `POST /turn/end` | Máquina de turnos del juego. `setup` clusteriza zonas entre jugadores y es sensible — exige el token compartido salvo en modo local (`USE_LOCAL_STORE=1`). |
| **`analiticas.py`** 🆕 | `GET /analytics/top-steps-month`, `GET /analytics/top-rainy-days`, `GET /analytics/top-bad-air`, `GET /analytics/user/{player_id}/history` | Lee `cloudrisk.player_scoring_events` × `environmental_factors` en BigQuery. Caché LRU 60 s para evitar un query por request. La página `/analytics` del frontend consume estos endpoints. |
| **`compatibilidad_equipo.py`** | `GET /state/locations`, `GET /state/player/{id}`, `POST /actions/place` | Rutas alias que mantienen compatibilidad con el contrato del equipo. |
| **`multiplicadores.py`** | `GET /multipliers/current` | Último multiplicador ambiental efectivo (cachea el último `environmental_factors`). |
| **`misiones.py`** | `GET /missions/`, `POST /missions/{id}/claim` | Misiones/achievements del juego. |

### `services/` — lógica de negocio transversal

| Archivo | Propósito |
|---|---|
| **`autenticacion.py`** | Emisión de JWT (`create_access_token`) + la dependencia FastAPI `get_current_user` que usan todas las rutas protegidas. El hashing con Bcrypt vive en `repositories/usuarios.py`. |
| **`asesor_ia.py`** | Asesor táctico gratis, sin coste de API. Dada una batalla, devuelve una pista de una línea basada en matemáticas simples de defensor/atacante. Lo usa `GET /battles/{id}/advice`. |
| **`gestor_websocket.py`** | Clase `ConnectionManager` que `main.py` instancia. Lleva registro de las conexiones WS abiertas por `user_id` y envía mensajes personales o broadcast. |


### `repositories/` — acceso a datos

Dos implementaciones detrás de los mismos nombres de función. Cada módulo comprueba `USE_LOCAL_STORE` al importarse y enlaza el backend en memoria o el cliente Firestore.

| Archivo | Respaldado por | Qué contiene |
|---|---|---|
| **`almacen_en_memoria.py`** | un `defaultdict` de Python | La implementación en memoria de `doc_set / doc_get / doc_query`, la lista canónica `VALENCIA_ZONES` (87 zonas) y las funciones `seed_zones()` + `seed_demo_players()` que se llaman al arrancar. |
| **`usuarios.py`** | colección Firestore `users` o en memoria | `create_user`, `get_user_by_email`, `verify_password`, `update_user`, `list_users_by_clan`. Bcrypt está aquí. |
| **`clanes.py`** | colección Firestore `clans` o en memoria | `create_clan`, `get_clan`, `list_clans`, `add_member`, `remove_member`, `delete_clan`. |
| **`zonas.py`** | colección Firestore `zones` o en memoria | `list_zones`, `get_zone_by_id`, `update_zone`, helpers point-in-polygon. |
| **`batallas.py`** | colección Firestore `battles` o en memoria | `create_battle`, `get_battle`, `list_ongoing_battles`, `resolve_battle`. |
| **`pasos.py`** | colección Firestore `step_logs` o en memoria | Log append-only de cada evento de sincronización de pasos. |
| **`publicador_pubsub.py`** | Pub/Sub real o no-op | Publica los tres topics del juego (`location-events`, `step-events`, `battle-events`). No hace nada en modo local. |

### `tests/`

| Archivo | Qué cubre |
|---|---|
| **`conftest.py`** | Fixture `client` (FastAPI TestClient con `USE_LOCAL_STORE=1`) y fixture `registered_user`. |
| **`prueba_salud.py`** | `/health` devuelve 200 + `{"status":"ok"}`. |
| **`prueba_zonas.py`** | `GET /api/v1/zones/` devuelve las 87 zonas de Valencia sembradas. |
| **`prueba_usuarios.py`** | Round-trip register / login / `/me`. Incluye un `xfail` estricto que documenta un bug real: `/users/me` filtra `hashed_password`; elimina el `xfail` cuando `routers/usuarios.py::get_me` lo filtre. |


## Cambiar entre local y Firestore

| Modo | Qué configuras | Dónde vive el dato |
|---|---|---|
| **Local (por defecto en dev)** | `USE_LOCAL_STORE=1` | RAM del proceso uvicorn. Se borra al reiniciar. Los 4 jugadores demo de `data/players.json` y las 87 zonas se vuelven a sembrar en cada arranque. |
| **Emulador Firestore** | `FIRESTORE_EMULATOR_HOST=localhost:8200` (y *sin definir* `USE_LOCAL_STORE`) | El emulador arrancado por `docker compose up`. Persiste durante la vida del contenedor del emulador. |
| **Firestore real (GCP)** | Ejecuta primero `gcloud auth application-default login`, luego exporta `PROJECT_ID=cloudrisk-492619` (o el tuyo), y quita `USE_LOCAL_STORE` y `FIRESTORE_EMULATOR_HOST`. | La base de datos real. Usa `python ../scripts/sembrar_firestore.py --project cloudrisk-492619` para poblarla. |

## Añadir un nuevo endpoint — checklist

1. Elige el archivo de router correcto bajo `routers/` (o crea uno nuevo y regístralo en `main.py`).
2. Añade un modelo Pydantic de request y un modelo Pydantic de response al inicio del archivo.
3. Implementa el handler. Si toca datos, llama a una función `*_repo` — nunca accedas directamente a `almacen_en_memoria` o `firestore`.
4. Si requiere auth, añade `current_user: dict = Depends(get_current_user)` a la firma.
5. Escribe un test en `tests/`.
6. Ejecuta `pytest` — todo tiene que seguir verde.

## Parámetros del juego

Definidos en `configuracion.py`, todos sobrescribibles por env:

| Variable env | Por defecto | Qué controla |
|---|---|---|
| `POWER_PER_STEPS` | 500 | Pasos que un jugador debe caminar para ganar 1 army. Aplicado por el pipeline Dataflow, no por el backend. |
| `DAILY_ARMY_CAP` | 50 | Tope diario de armies/jugador (aplica en el pipeline). |
| `DAILY_STEPS_CAP` | 30000 | Tope diario de pasos contables/jugador (anti-trampa, aplica en el pipeline). |
| `MAX_SPEED_KMH` | 15 | Umbral velocidad; eventos por encima van a la DLQ de BQ. |
| `MIN_GARRISON` | 2 | Invariante: toda zona con owner mantiene ≥ 2 armies (aplicado en `zonas.py` tras conquista y en `ejercitos.py` en `fortify`). |
| `BATTLE_DURATION_HOURS` | 2 | Cuánto tiempo permanece abierta una batalla antes de resolverse. |
| `CLOUDRISK_MIN_MEMBERS` | 3 | Tamaño mínimo de clan necesario para reclamar una zona (actualmente informativo). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 10080 (7 días) | Tiempo de vida del JWT. |
| `SCHEDULER_SECRET` | — | Token compartido con Cloud Scheduler para invocar endpoints internos (`/turn/setup`, `/battles/resolve-expired`). |
| `USE_LOCAL_STORE` | `0` | Si `=1`, usa `almacen_en_memoria` y permite `/turn/setup` sin token (desarrollo). |

## Novedades 2026-04 (refactor)

- **`analiticas.py`** es nuevo — expone la analítica histórica que antes pintaba
  el dashboard Streamlit (retirado).
- **`/zones/{id}/attack`** es el sistema canónico de combate (Risk dice) y ha
  corregido un `NameError` en los imports (`adyacencia as adjacency`, `dados as dice`).
- **`/turn/setup`** ahora exige `X-Scheduler-Token` en producción. En local
  (`USE_LOCAL_STORE=1`) sigue siendo abierto para no romper tests.
- **`/battles/*`** está marcado `deprecated=True` — se mantiene para histórico
  y para el cron `resolve-expired`.
- Invariante **`MIN_GARRISON=2`**: tres sitios tocados para mantenerla
  (`zonas.py` tras conquista, `ejercitos.py` en `fortify`, `turno.py` en setup).
