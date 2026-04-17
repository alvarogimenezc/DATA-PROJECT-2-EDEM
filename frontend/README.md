# frontend/

## 🎯 Qué hace este directorio

Es la **aplicación web del juego**: el mapa de Valencia interactivo, el login de los comandantes, el panel de clan, la conquista de zonas y la vista de batallas en curso. Lo que ve el jugador.

Construida como SPA con **React + Vite**, renderiza el mapa con **MapLibre GL** (fork open-source de Mapbox, sin token de pago), y habla con el `backend/` por REST + WebSocket para los eventos en vivo.

Se despliega como **Cloud Run Service** (`cloudrisk-web`) detrás de un `nginx` que sirve los estáticos compilados.

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **React 18** | Estándar de facto para SPAs. El equipo ya lo conoce; el ecosistema (hooks, router, context) nos deja evitar un framework más pesado. |
| **Vite 5** | Dev server instantáneo (HMR < 100 ms) y build optimizado. Mucho más ágil que Webpack para el tamaño del proyecto. |
| **TypeScript / JSX** | Actualmente `.jsx` (no TS estricto) para iterar rápido en clase. El `vite.config.js` está listo para migrar. |
| **MapLibre GL 4** | El mapa. Fork libre de Mapbox GL: las mismas APIs (layers, sources, popups) pero sin API key. Importante porque la demo va en proyecto educativo. |
| **TailwindCSS** | Estilos por utilidades. Evita escribir CSS custom para cada componente y mantiene la UI consistente. |
| **framer-motion** | Animaciones del HUD (conquistas, recompensas, dados). |
| **axios** | Cliente HTTP al backend. Más cómodo que `fetch` para interceptores de auth JWT. |
| **nginx** (imagen final) | Sirve el bundle estático en `:8080`. Multi-stage Docker: Node solo para build, nginx para runtime. |

## 📂 Archivos principales

| Archivo / Carpeta | Qué hace |
|---|---|
| `package.json` | Dependencias (react, vite, maplibre-gl, tailwind, axios, framer-motion). |
| `vite.config.js` | Config de Vite: plugin React, alias, variables `VITE_*` expuestas al cliente. |
| `Dockerfile` | Multi-stage: `node:20-alpine` para `npm run build`, luego `nginx:1.27-alpine` sirviendo `/dist`. |
| `nginx.conf` | Config nginx: servir SPA con fallback a `index.html` para React Router. |
| `tailwind.config.js` | Purga y tema de Tailwind. |
| `src/` | Código fuente: `App.jsx`, `pages/`, `components/`, `hooks/`, `contexts/`, `api/`. |
| `public/` | Assets estáticos (favicons, imágenes de reel de recompensas). |

## 🔗 Cómo se conecta con el resto del proyecto

```
frontend/  ──(HTTP REST)──▶  backend/  (/auth, /zones, /clans, /armies, /battles)
           ──(WebSocket)──▶  backend/  (eventos live: conquest, battle-start)

Build time: Cloud Build inyecta VITE_API_URL y VITE_WS_URL tras deploy del backend
            (ver CICD/cloudbuild.yaml paso `get-api-url`)

Runtime:    nginx sirve el bundle en :8080  ──▶  Cloud Run Service cloudrisk-web
```

- **Depende 100 %** del `backend/`: sin API el login no funciona.
- El **dashboard** es un servicio aparte (Streamlit), no se embebe en el frontend.
- Terraform (`08_cloud_run.tf`) crea el service `cloudrisk-web` y expone la URL pública.

## 🚀 Cómo ejecutarlo

```bash
# Dev local con Vite (HMR)
cd frontend
npm install
VITE_API_URL=http://localhost:8080 VITE_WS_URL=ws://localhost:8080 npm run dev
# abre http://localhost:5173

# Build de producción (genera frontend/dist/)
npm run build
npm run preview    # sirve el build en :4173 para probar

# Docker local (multi-stage, termina sirviendo en :8080)
docker build \
  --build-arg VITE_API_URL=http://localhost:8080 \
  --build-arg VITE_WS_URL=ws://localhost:8080 \
  -t cloudrisk-frontend ./frontend
docker run --rm -p 8080:8080 cloudrisk-frontend

# Deploy manual a Cloud Run (el script del equipo pasa VITE_API_URL por build-arg)
bash CICD/desplegar_manual.sh frontend
```

Variables de entorno (inyectadas **en build**, no runtime — Vite las hornea en el bundle):

| Var | Ejemplo | Para qué |
|---|---|---|
| `VITE_API_URL` | `https://cloudrisk-api-xxxx.run.app` | Endpoint REST del backend. |
| `VITE_WS_URL` | `wss://cloudrisk-api-xxxx.run.app` | Endpoint WebSocket (derivado de API URL). |
