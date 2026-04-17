# CloudRisk 492619 — Guía de Inicio Rápido 🚀

Proyecto de microservicios orquestado con **Docker Compose** y autenticado contra GCP mediante **ADC (Application Default Credentials)**.

## 🛠 Requisitos previos

- [Docker & Docker Compose](https://www.docker.com/)
- [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)

---

## 🔐 Configuración de acceso (solo la primera vez)

### 1. Solicitar acceso al proyecto GCP
Pide al admin del proyecto `cloudrisk-492619` que te añada con rol Editor:

```bash
# Lo ejecuta el admin:
gcloud projects add-iam-policy-binding cloudrisk-492619 \
  --member=user:tu-email@gmail.com \
  --role=roles/editor
```

### 2. Autenticación local
En tu terminal:

```bash
# Login en el navegador
gcloud auth login

# Generar credenciales ADC para aplicaciones
gcloud auth application-default login

# Fijar el proyecto
gcloud config set project cloudrisk-492619
```

---

## 🏗 Configuración del entorno

### 1. Clonar el repo
```bash
git clone <URL-DEL-REPO>
cd <NOMBRE-DEL-REPO>
```

### 2. Variables de entorno
```bash
cp .env.example .env
```

Abre `.env` y rellena `ADC_PATH` con la ruta al JSON que generó `gcloud` en el paso anterior:

- **Linux/Mac:** `/home/TU_USUARIO/.config/gcloud/application_default_credentials.json`
- **Windows:** `C:/Users/TU_USUARIO/AppData/Roaming/gcloud/application_default_credentials.json`

---

## 🚀 Ejecución del proyecto

```bash
docker compose up --build
```

Docker montará automáticamente tus credenciales dentro de los contenedores, y las apps podrán hablar con **Firestore**, **BigQuery** y **Pub/Sub** de forma segura usando tu identidad.

Para parar todo:
```bash
docker compose down
```

---

## 🔍 ¿Qué significa `${ADC_PATH}:/tmp/adc.json:ro`?

En el `docker-compose.yml` verás esta línea en los servicios:

```yaml
volumes:
  - ${ADC_PATH}:/tmp/adc.json:ro
```

Es un **bind mount**: monta un archivo de tu máquina dentro del contenedor. Se lee en 3 partes separadas por `:`

```
${ADC_PATH}         :  /tmp/adc.json    :  ro
    ↑                       ↑               ↑
origen (host)        destino (contenedor)  modo
```

### 1. `${ADC_PATH}` — origen (en TU máquina)
Docker Compose sustituye esta variable con lo que tengas en tu `.env`. Ejemplo:
```
# Linux/Mac:
/home/TU_USUARIO/.config/gcloud/application_default_credentials.json
# Windows:
C:/Users/TU_USUARIO/AppData/Roaming/gcloud/application_default_credentials.json
```
Es el JSON que generó `gcloud auth application-default login`.

### 2. `/tmp/adc.json` — destino (dentro del contenedor)
Dentro del contenedor, ese mismo archivo aparece como si estuviera en `/tmp/adc.json`. Es una ruta virtual que solo existe dentro del contenedor. Por eso en el `.env` tienes:
```
GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json
```
Las librerías de Google (`google-cloud-pubsub`, `firestore`, `bigquery`, etc.) leen esa variable y abren ese path → encuentran tu JSON real → se autentican con tu cuenta Google.

### 3. `ro` — read-only
El contenedor **solo puede leer** el archivo, nunca modificarlo ni borrarlo. Es una protección: si el código se vuelve loco, no puede corromper tus credenciales reales.

### Analogía
Es como crear un acceso directo dentro del contenedor que apunta a un archivo tuyo. El contenedor "ve" el archivo sin que tengas que copiarlo, y **cada compañero monta el suyo propio** → cada uno usa su identidad de Google sin compartir nada.

### Por qué así y no metiendo el JSON en la imagen
- **Seguridad**: la imagen Docker es portable/compartible; si metieras el JSON dentro, lo regalarías al mundo.
- **Flexibilidad**: cada compañero tiene su propio ADC en un path distinto → con `${ADC_PATH}` cada uno pone el suyo en `.env` sin tocar el `docker-compose.yml`.

---

## 📂 Estructura del proyecto

- `/data_generator` — **Walker**: simula un jugador caminando por Valencia y publica posiciones a Pub/Sub.
- `/consumer` — Lector PULL de Pub/Sub (solo debug, imprime por pantalla).
- `/backend` — **API REST (FastAPI)** con la lógica de negocio del juego (estado del jugador, acciones sobre zonas).
- `/frontend` — Interfaz de usuario (Ricardo).
- `/weather_airq` — Ingestores de calidad del aire y tiempo (Álvaro).
- `/pipelines` — Pipeline Dataflow / Beam (Noelia + Martha).
- `/scripts` — **Comandos sueltos** que el equipo ejecuta a mano (crear tablas BQ, probar endpoints con curl, deploy manual).
- `/cicd` — **Plantillas de Cloud Build** que se ejecutan automáticamente con `git push` (deploy a Cloud Run).
- `/docs` — Documentación extendida.

---

## 🎮 Frontend

SPA React 18 + Vite + MapLibre GL que muestra el mapa 3D de Valencia con los distritos del juego, panel de stats, misiones y leaderboard.

### Arrancar en desarrollo local

```bash
cd frontend
npm install
cp .env.example .env      # edita con la URL del backend
npm run dev               # http://localhost:3000
```

### Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `VITE_API_URL` | URL base del backend (HTTP) | `http://localhost:8080` |
| `VITE_WS_URL` | URL del WebSocket del backend | `ws://localhost:8080` |

En producción Vite "hornea" estos valores en el bundle durante `npm run build`. Se pasan como `--build-arg` al Dockerfile.

### Build + Docker local

```bash
cd frontend
docker build \
  --build-arg VITE_API_URL=http://localhost:8080 \
  --build-arg VITE_WS_URL=ws://localhost:8080 \
  -t frontend:dev .
docker run --rm -p 3000:8080 frontend:dev
# → http://localhost:3000
```

### Deploy a Cloud Run

```bash
gcloud builds submit frontend/ \
  --tag europe-west1-docker.pkg.dev/cloudrisk-492619/cloudrisk/frontend:latest \
  --project cloudrisk-492619

gcloud run deploy cloudrisk-frontend \
  --image europe-west1-docker.pkg.dev/cloudrisk-492619/cloudrisk/frontend:latest \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 \
  --project cloudrisk-492619
```

---

## ⚙️ Backend API

Endpoints que expone el backend (puerto `8080`, prefijo `/api/v1`):

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Liveness/readiness probe |
| GET | `/api/v1/state/player/{player_id}` | Estado del jugador (ejércitos y pasos totales) |
| GET | `/api/v1/state/locations` | Lista de zonas del mapa con ejércitos |
| POST | `/api/v1/actions/place` | Registra "poner N ejércitos en una zona" |

Documentación interactiva (Swagger): **`http://localhost:8080/api/v1/docs`**

### 🏛️ Arquitectura en capas

El backend está organizado en **capas separadas** para que cada archivo haga una sola cosa:

```
backend/
└── cloudrisk_api/
    ├── main.py                  # 👔 monta la app FastAPI y registra los endpoints
    ├── config.py                # ⚙️ variables de entorno (pydantic_settings)
    ├── endpoints/               # 🍽️ "camareros": reciben HTTP, validan, llaman a la BD
    │   ├── estado.py            #    GET /state/player/...  GET /state/locations
    │   └── acciones.py          #    POST /actions/place
    └── database/                # 👨‍🍳 "cocineros": hablan con Firestore y BigQuery
        ├── firestore_db.py
        └── bigquery_db.py
```

**Analogía rápida:** un restaurante. Los archivos de `endpoints/` son **camareros** que toman tu pedido en la mesa; los archivos de `database/` son **cocineros** que hablan con la nevera y el fuego; `main.py` es el **dueño** que monta el local y enciende las luces.

### ✅ Ventajas de esta separación

- **Cambiar de base de datos no rompe nada**
  Si mañana cambiamos BigQuery por otra cosa (Postgres, ClickHouse, lo que sea), **solo se toca `database/bigquery_db.py`**. Los archivos de `endpoints/` ni se enteran. Lo mismo con Firestore.

- **Añadir un endpoint nuevo es trivial**
  Creas un archivo nuevo en `endpoints/` (o añades una función a uno existente) y ya está. **No tocas la lógica de negocio que ya funcionaba**, así que no hay riesgo de romper nada.

- **Tests sin levantar FastAPI**
  Los archivos de `database/` son funciones normales de Python. Puedes testearlas con `pytest` directamente, sin tener que arrancar un servidor HTTP. Más rápido y más limpio.

- **Estilo estándar de la industria**
  Es la arquitectura por capas que se usa en proyectos profesionales (también la que usa el repo del profe). Cualquier persona que se incorpore al equipo entiende el código en 5 minutos.

---

## 📁 ¿Qué es la carpeta `CICD/`?

Contiene **todo lo relacionado con desplegar y operar el proyecto**: scripts manuales para el día a día y plantillas automáticas de Cloud Build. **CI/CD** significa *"Continuous Integration / Continuous Deployment"*: que cada vez que alguien hace `git push`, GCP construya la imagen Docker y la despliegue a Cloud Run sola, sin que nadie toque nada.

### 🛠 Scripts manuales (los lanzas tú a mano)

| Script | Para qué sirve | Cuándo se ejecuta |
|---|---|---|
| `CICD/crear_tablas_bigquery.sh` | Crea las tablas de BigQuery (`user_actions`) | **Una sola vez**, al montar el proyecto desde cero |
| `CICD/probar_api.sh` | Hace `curl` a todos los endpoints del backend | Cada vez que quieras probar que la API responde bien |
| `CICD/desplegar_manual.sh` | Build + deploy manual a Cloud Run desde tu portátil | Cuando quieres desplegar sin esperar al CI/CD |

### ⚙️ Plantillas Cloud Build (las lanza GCP solo con `git push`)

| Archivo | Qué construye | Dónde lo despliega |
|---|---|---|
| `CICD/desplegar_backend_auto.yml` | Imagen Docker del backend | Cloud Run (servicio HTTP en `:8080`) |
| `CICD/desplegar_walker_auto.yml` | Imagen Docker del walker | Cloud Run Job (proceso continuo) |
| `CICD/README.md` | Instrucciones para conectar los triggers de GitHub | (documentación) |

### Diferencia entre `desplegar_manual.sh` y los `*.yml`

- **`CICD/desplegar_manual.sh`** → tú lanzas el deploy **a mano** desde tu portátil cuando tú quieras.
- **`CICD/*.yml`** → el deploy se lanza **solo**, cada vez que haces `git push` a `main`.

Los dos hacen lo mismo (construir imagen + desplegar). La diferencia es **quién aprieta el botón**: tú a mano (`desplegar_manual.sh`) o GCP automático (los YAML).

**Analogía:** `desplegar_manual.sh` es lavarte los platos a mano cuando tú decides; los `*.yml` son el lavavajillas que se enciende solo cuando metes los platos sucios.

### Probar el backend localmente
```bash
# 1. Crear la tabla BigQuery (una sola vez)
bash CICD/crear_tablas_bigquery.sh

# 2. Levantar todo
docker compose up --build

# 3. En otra terminal
bash CICD/probar_api.sh
```

---

## ☁️ Deploy a Cloud Run

```bash
# Todo de golpe
bash CICD/desplegar_manual.sh

# Solo backend
bash CICD/desplegar_manual.sh backend

# Solo walker (como Cloud Run Job)
bash CICD/desplegar_manual.sh walker
```

El script es idempotente: crea el repo de Artifact Registry si no existe, sube la imagen con Cloud Build y despliega en Cloud Run.

---

## 🔁 CI/CD con Cloud Build (estilo profe)

Plantillas en `CICD/`:
- `CICD/desplegar_backend_auto.yml` — build + deploy del backend a Cloud Run.
- `CICD/desplegar_walker_auto.yml` — build + deploy del walker como Cloud Run Job.

Lanzar manualmente:
```bash
gcloud builds submit . --config=CICD/desplegar_backend_auto.yml --project=cloudrisk-492619
gcloud builds submit . --config=CICD/desplegar_walker_auto.yml  --project=cloudrisk-492619
```

Para conectar triggers automáticos en `git push`, ver [`CICD/README.md`](CICD/README.md).

---

## 👥 Reparto del equipo

Quién hace qué en el proyecto: [`docs/REPARTO_EQUIPO.md`](docs/REPARTO_EQUIPO.md)

Documentación extra:
- [`docs/EXPLICACION.md`](docs/EXPLICACION.md) — Walkthrough visual del sistema con diagramas.
- [`docs/RESUMEN_EQUIPO.md`](docs/RESUMEN_EQUIPO.md) — Update en primera persona para el equipo.

---

## 🆘 Problemas comunes

- **`Could not load the default credentials`** → Revisa que `ADC_PATH` en `.env` apunte a un archivo existente.
- **`PERMISSION_DENIED`** → Pide al admin que te añada al IAM del proyecto.
- **Docker no arranca** → Asegúrate de que Docker Desktop está corriendo.
