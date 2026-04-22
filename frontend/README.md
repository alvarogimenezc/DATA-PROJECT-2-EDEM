# Frontend — CloudRISK

La parte del proyecto que ve el jugador. Es un juego de conquista de zonas sobre el mapa real de Valencia, construido como una SPA en React que habla con el backend por REST y WebSocket.

---

## Qué tecnologías usa y por qué

| Tech | Versión | Motivo |
|---|---|---|
| React | 18.3.1 | SPA con hooks y contexto, sin necesidad de framework más pesado |
| Vite | 5.3.1 | Dev server con recarga instantánea, build rápido y optimizado |
| MapLibre GL | 4.4.0 | Renderiza el mapa interactivo; es el fork libre de Mapbox, sin API key de pago |
| TailwindCSS | 3.4.19 | Utilidades CSS para que el tema táctico sea coherente sin escribir CSS por componente |
| framer-motion | 12.38.0 | Animaciones del HUD: conquistas, recompensas, dados |
| lucide-react | 1.7.0 | Iconos que reemplazan emojis en el HUD |
| axios | 1.7.2 | Cliente HTTP con interceptor JWT y auto-logout al recibir un 401 |
| react-router-dom | 6.23.1 | Dos rutas: `/` para el juego y `/analytics` para el dashboard histórico |
| nginx 1.27-alpine | — | Sirve los estáticos compilados en el contenedor final |

El Docker es multi-stage: `node:20-alpine` compila el proyecto con Vite, y `nginx:1.27-alpine` sirve el resultado. La imagen de node no llega a producción.

---

## Cómo se conecta con el resto del proyecto

```
frontend/
  ──(HTTP REST)──▶  backend/   → /auth, /zones, /clans, /armies, /battles, /turn, /analytics
  ──(WebSocket)──▶  backend/   → eventos en tiempo real: conquistas, batallas, pong

GeoJSON (en public/):
  valencia_original_57.geojson   → las 57 zonas jugables del mapa
  valencia_districts.geojson     → distritos de contexto

Build time:
  VITE_API_URL y VITE_WS_URL se pasan como --build-arg al docker build.
  Vite los hornea en el bundle JS. En runtime nginx no sabe nada de ellos.
  La URL del API viene de: terraform output -raw api_url

Deploy:
  Terraform crea el Cloud Run Service "cloudrisk-web" y le da la URL pública.
  El servicio escucha en :8080 (nginx).
```

El frontend no puede funcionar sin el backend. Si el API no responde, el auto-login falla y la app se queda en blanco.

---

## Estructura de archivos relevante

```
frontend/
├── public/
│   ├── valencia_original_57.geojson   ← zonas del juego
│   └── valencia_districts.geojson     ← distritos de contexto
├── src/
│   ├── App.jsx                        ← router raíz
│   ├── api/
│   │   ├── client.js                  ← axios singleton con interceptor 401
│   │   └── analiticas.js              ← fetchers para los endpoints de analytics
│   ├── contexts/
│   │   └── AuthContext.jsx            ← auto-login con jugadores de lobby
│   ├── hooks/
│   │   └── useWebSocket.js            ← conexión WS con reconexión automática
│   ├── pages/
│   │   ├── UrbanPacer.jsx             ← página principal: mapa + HUD + paneles
│   │   └── Analytics.jsx              ← dashboard de datos históricos
│   ├── components/                    ← paneles y elementos del HUD
│   └── styles/
│       ├── urban-pacer.css            ← estilos del mapa y HUD
│       └── tactical-ui.css            ← tema táctico (paneles, botones)
├── Dockerfile
├── nginx.conf
├── vite.config.js
└── package.json
```

---

## Autenticación: cómo entran los jugadores

No hay formulario de login. Al arrancar, `AuthContext` elige automáticamente uno de cuatro jugadores preconfigurados en el backend y hace login con él.

| Jugador | Email | Color en el mapa |
|---|---|---|
| Norte | norte@cloudrisk.app | rojo (#f43f5e) |
| Sur | sur@cloudrisk.app | amarillo (#facc15) |
| Este | este@cloudrisk.app | cian (#06b6d4) |
| Oeste | oeste@cloudrisk.app | morado (#a855f7) |

Por defecto entras como Norte. Para cambiar de jugador, añade `?player=sur` (o `este`, `oeste`) a la URL.

El JWT que devuelve el backend se guarda en `localStorage` bajo la clave `cloudrisk_token`. Si al recargar el token sigue siendo válido, se reutiliza directamente. Si ha caducado (por ejemplo porque el backend se reinició y limpió su store en memoria), se hace re-login automático. Cualquier 401 en una petición dispara el interceptor de axios, que hace logout y recarga la página.

---

## Páginas

### `/` — UrbanPacer

La página principal. Combina el mapa MapLibre con el HUD y los paneles de acción.

Incluye un singleton `_turnPoll` que consulta `/api/v1/turn/` cada 3 segundos. Todos los componentes que necesitan el estado del turno (banner, botón de fin de turno, botón de bots) se suscriben a este singleton en lugar de hacer polling por separado, lo que reduce las peticiones al backend en 4×.

### `/analytics`

Dashboard con datos históricos del pipeline Dataflow → BigQuery. Tiene cuatro pestañas:

| Pestaña | Endpoint del backend | Qué muestra |
|---|---|---|
| Top pasos (30d) | GET /analytics/top-steps-month | Jugadores con más pasos en el último mes |
| Top lluvia | GET /analytics/top-rainy-days | Los más activos en días lluviosos |
| Top mala calidad aire | GET /analytics/top-bad-air | Los más activos con mala calidad del aire |
| Rechazos anti-trampa | GET /analytics/anti-cheat-rejects | Pasos rechazados por el sistema anti-cheat |

Si BigQuery todavía no tiene datos (pipeline no ha corrido), las tablas muestran un mensaje explicativo en lugar de fallar.

---

## Componentes del juego

| Componente | Qué hace |
|---|---|
| `HUD.jsx` | Barra superior con nombre, rango, stats. Incluye la lógica de tres modos de vista del mapa (Control / Presión / Economía) que se implementaron como funcionalidad opcional y no llegaron a conectarse al HUD activo — no hay botones expuestos al usuario. |
| `GameMap.jsx` | Capa MapLibre sobre el GeoJSON de Valencia. Colorea zonas por facción según quién las controla. |
| `ArmyPanel.jsx` | Panel de despliegue de tropas en la zona seleccionada. Muestra el balance actual y sugiere una cantidad razonable. |
| `BattlePanel.jsx` | Panel de ataque con dados animados al estilo Risk. Muestra batallas activas y permite pedir consejo táctico al backend. |
| `FortifyPanel.jsx` | Mover tropas entre zonas propias. Muestra solo las zonas donde el jugador tiene al menos una tropa. |
| `Leaderboard.jsx` | Clasificación global de jugadores. |
| `RewardChest.jsx` | Animación de recompensa al conquistar una zona. |
| `SettingsPanel.jsx` | Configuración in-game (volumen y preferencias). |
| `WarTutorial.jsx` | Tutorial de bienvenida que aparece la primera vez. Se guarda en `localStorage` para no volver a mostrarse. |

---

## WebSocket

El hook `useWebSocket.js` mantiene una conexión con `${VITE_WS_URL}/ws/{userId}` para recibir eventos de juego en tiempo real (conquistas, inicio de batalla, pong).

- **Reconexión automática**: si se cae la conexión, reintenta con backoff exponencial empezando en 1s y doblando hasta 30s, con un máximo de 10 intentos. Después de 10 fallos el estado queda en `failed`.
- **Heartbeat**: envía un ping JSON cada 25s para que Cloud Run no cierre la conexión por inactividad.
- **Eventos de red**: si el navegador detecta que se va la red (`offline`), cierra el socket y cancela los timers. Cuando vuelve la red (`online`), reconecta de inmediato.

---

## Cómo ejecutarlo

```bash
# Dev local con recarga en caliente (http://localhost:5173)
cd frontend
npm install
VITE_API_URL=http://localhost:8080 VITE_WS_URL=ws://localhost:8080 npm run dev

# Cambiar de jugador en dev
open "http://localhost:5173?player=sur"   # norte | sur | este | oeste

# Build de producción (genera frontend/dist/)
npm run build

# Docker local (sirve en http://localhost:8080)
docker build \
  --build-arg VITE_API_URL=http://localhost:8080 \
  --build-arg VITE_WS_URL=ws://localhost:8080 \
  -t cloudrisk-frontend ./frontend
docker run --rm -p 8080:8080 cloudrisk-frontend
```

### Variables de entorno

Se inyectan en el momento del build (no en runtime). Vite las hornea en el bundle JS, así que no se pueden cambiar sin recompilar.

| Variable | Ejemplo | Para qué |
|---|---|---|
| `VITE_API_URL` | `https://cloudrisk-api-xxxx.run.app` | Endpoint REST del backend |
| `VITE_WS_URL` | `wss://cloudrisk-api-xxxx.run.app` | Endpoint WebSocket del backend |

