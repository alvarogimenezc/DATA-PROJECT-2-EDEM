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
| **`zonas.py`** | `GET /zones/`, `GET /zones/{id}`, `POST /zones/{id}/conquer` + helper WebSocket `handle_location_update()` | Los 87 barrios de Valencia. El helper WS se invoca desde `main.py` cada vez que el frontend envía un evento `location_update`. |
| **`batallas.py`** | `POST /battles/`, `GET /battles/`, `GET /battles/{id}`, `GET /battles/{id}/advice`, `POST /battles/{id}/resolve` | Combate: declarar una batalla sobre una zona enemiga, obtener una pista táctica de la IA, resolverla. |
| **`pasos.py`** | `POST /steps/sync`, `GET /steps/history` + helper WS `handle_step_update()` | Los pasos del mundo real de los jugadores convertidos en puntos de poder en el juego. |
| **`ejercitos.py`** | `GET /armies/balance`, `POST /armies/place`, `GET /armies/locations`, `POST /armies/fortify` | Desplegar / mover tropas entre zonas propias. **Estas son las rutas en las que solapa el backend CloudRISK del equipo — mira [`services/adaptador_cloudrisk.py`](./cloudrisk_api/services/adaptador_cloudrisk.py).** |

### `services/` — lógica de negocio transversal

| Archivo | Propósito |
|---|---|
| **`autenticacion.py`** | Emisión de JWT (`create_access_token`) + la dependencia FastAPI `get_current_user` que usan todas las rutas protegidas. El hashing con Bcrypt vive en `repositories/usuarios.py`. |
| **`asesor_ia.py`** | Asesor táctico gratis, sin coste de API. Dada una batalla, devuelve una pista de una línea basada en matemáticas simples de defensor/atacante. Lo usa `GET /battles/{id}/advice`. |
| **`gestor_websocket.py`** | Clase `ConnectionManager` que `main.py` instancia. Lleva registro de las conexiones WS abiertas por `user_id` y envía mensajes personales o broadcast. |
| **`adaptador_cloudrisk.py`** | Proxy opcional al backend CloudRISK del equipo (alvarogimenezc/DATA-PROJECT-2-EDEM). Se activa con `CLOUDRISK_API_URL`. Expone `get_locations()`, `get_player_state()`, `place_armies()`. |

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
| **`prueba_adaptador_cloudrisk.py`** | El adapter está desactivado cuando `CLOUDRISK_API_URL` no está definido, y activado (con la barra final normalizada) cuando sí lo está. |

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
| `POWER_PER_STEPS` | 100 | Pasos que un jugador debe caminar para ganar 1 punto de poder. |
| `BATTLE_DURATION_HOURS` | 2 | Cuánto tiempo permanece abierta una batalla antes de resolverse. |
| `CLOUDRISK_MIN_MEMBERS` | 3 | Tamaño mínimo de clan necesario para reclamar una zona (actualmente informativo). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 10080 (7 días) | Tiempo de vida del JWT. |
