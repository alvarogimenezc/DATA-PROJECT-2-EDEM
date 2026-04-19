# Backend — CloudRISK API

API REST del juego CloudRISK, construida con **FastAPI** (Python). Expone todos los endpoints que consume el frontend y un WebSocket para eventos en tiempo real.

## Estructura de carpetas

```
backend/
├── cloudrisk_api/
│   ├── main.py              ← Punto de entrada FastAPI
│   ├── configuracion.py     ← Variables de entorno y parámetros del juego
│   ├── endpoints/           ← Rutas HTTP (cada fichero = un recurso)
│   ├── services/            ← Lógica de negocio (auth, dados, turnos, WS)
│   └── database/            ← Acceso a datos (Firestore o memoria)
├── tests/                   ← Tests con pytest
├── Dockerfile
└── requirements.txt
```

---

## Endpoints

Todas las rutas van bajo `/api/v1`. Autenticación por JWT (Bearer token).

| Fichero | Prefijo | Qué hace |
|---------|---------|----------|
| `usuarios.py` | `/users` | Registro, login y perfil |
| `clanes.py` | `/clans` | Crear/unirse/salir de clanes |
| `zonas.py` | `/zones` | Listar los 87 barrios, conquistar y atacar (dados Risk) |
| `ejercitos.py` | `/armies` | Desplegar y mover tropas |
| `turno.py` | `/turn` | Fases del turno: refuerzo → ataque → fortificación |
| `pasos.py` | `/steps` | Sincronizar pasos reales → generar ejércitos |
| `misiones.py` | `/missions` | Misiones diarias con recompensas |
| `multiplicadores.py` | `/multipliers` | Multiplicador ambiental (aire × clima) |
| `analiticas.py` | `/analytics` | Consultas analíticas a BigQuery |
| `compatibilidad_equipo.py` | `/state`, `/actions` | Rutas de compatibilidad con el contrato del equipo |
| `batallas.py` ⚠️ | `/battles` | Sistema de combate legacy (deprecated) |

---

## Servicios

| Fichero | Qué hace |
|---------|----------|
| `autenticacion.py` | Genera y valida tokens JWT |
| `dados.py` | Motor de combate con dados tipo Risk |
| `estado_juego.py` | Estado del turno actual (jugador, fase) |
| `gestor_websocket.py` | Gestiona conexiones WebSocket (broadcast y mensajes) |
| `multiplicadores.py` | Caché del multiplicador ambiental |
| `adyacencia.py` | Grafo de adyacencia entre barrios (desde GeoJSON) |
| `asesor_ia.py` | Consejo táctico para batallas (determinista) |

---

## Capa de datos

Cada módulo de `database/` funciona con **Firestore** en producción o con un **almacén en memoria** en local (`USE_LOCAL_STORE=1`). El cambio es transparente.

| Fichero | Colección / recurso |
|---------|---------------------|
| `usuarios.py` | `users` — CRUD de jugadores, hash bcrypt |
| `clanes.py` | `clans` — CRUD de clanes |
| `zonas.py` | `zones` — 87 barrios de Valencia, conquista atómica |
| `batallas.py` | `battles` — batallas (sistema legacy) |
| `pasos.py` | `step_logs` — historial de pasos sincronizados |
| `publicador_pubsub.py` | Pub/Sub — publica eventos de pasos, ubicación y batallas |
| `almacen_en_memoria.py` | Implementación en RAM para desarrollo local |

---

## Modos de ejecución

| Modo | Configuración | Datos |
|------|---------------|-------|
| **Local (RAM)** | `USE_LOCAL_STORE=1` | En memoria, se reinicia cada vez. Siembra 87 zonas + 4 jugadores demo. |
| **Emulador Firestore** | `FIRESTORE_EMULATOR_HOST=localhost:8200` | Persiste mientras el contenedor esté vivo. |
| **GCP producción** | `PROJECT_ID=cloudrisk-492619` + credenciales | Firestore + Pub/Sub + BigQuery reales. |

---

## Tests

```bash
cd backend
pytest
```

12 ficheros de test bajo `tests/`, todos corren contra el almacén en memoria (sin necesitar GCP). Cubren: usuarios, clanes, zonas, ejércitos, turnos, pasos, misiones, multiplicadores y salud.
