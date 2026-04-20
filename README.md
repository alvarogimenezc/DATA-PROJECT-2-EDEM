# CloudRISK — Serverless Urban Conquest

**Camina Valencia. Cada paso es munición. Conquista los 87 barrios.**

Proyecto 100 % **serverless** sobre Google Cloud Platform. Juego de estrategia geolocalizado tipo *Risk* sobre Valencia, construido como pipeline de datos **100 % serverless** en GCP.

## Índice
  - 1) Qué es CloudRISK
  - 2) Arquitectura
  - 3) Reglas del juego
  - 4) Flujo de datos
  - 5) Estructura de tablas — Firestore & BigQuery
  - 6) Arranque rápido en local
  - 7) Despliegue a GCP
  - 8) Arquitectura detallada

---

## 1. Qué es CloudRISK

Los ejércitos y el oro de cada jugador **no se regalan**: salen de los pasos
que da en la vida real. Un pipeline streaming los valida (anti-trampa + caps),
los convierte en tropas y los escribe en Firestore; desde ahí el jugador los
despliega en el mapa.

Objetivo educativo: aplicar Pub/Sub, Dataflow stateful, Firestore, BigQuery,
Cloud Run y Terraform sobre un caso de uso real, sin un solo servidor encendido
permanentemente (salvo el job de Dataflow, que por diseño mantiene estado).

---

## 2. Arquitectura

La arquitectura seleccionada para la resolución del reto es la siguiente: 

![Texto alternativo](DataProject2.jpg)

Como vemos, se trata de una arquitectura que respeta la filosofía habitual de proyectos de big data: ingesta — transformación — almacenamiento — visualización.

En nuestro caso, tenemos una ingesta de datos de geolocalización de usuarios, factor de calidad ambiental y calidad del aire. Estos datos entran a Dataflow donde se aplica la lógica de negocio y como resultado se insertan los ejércitos equivalentes ganados por el usuario tanto en Firestore como en BigQuery.

Firestore alberga las tablas de estado; en él tenemos las tablas `user_balance` y `location_balance`, que se actualizan conforme avanza la partida con los ejércitos disponibles por usuario y las zonas del mapa con los ejércitos y el usuario que las controla.

La base de datos de BigQuery nos sirve para almacenar datos históricos para métricas y análisis más profundos.

Por último, el frontend se conecta a las tablas mediante un servidor de FastAPI que sirve como puerta de acceso a las bases de datos. Además, las acciones de los usuarios en la aplicación también interactúan con las bases de datos mediante este servidor de entrada.

---

## 3. Reglas del juego

**CloudRISK** traslada la mecánica de conquista de territorios a la vida real. La economía del juego no avanza por el paso del tiempo, sino por la actividad física del usuario.

**1. Generación de Tropas y Multiplicadores:**
La conversión base del juego es de **500 pasos = 1 Ejército**. Sin embargo, este valor es dinámico y depende de las condiciones ambientales de Valencia en el momento exacto en que se camina:
* **Clima:** Días despejados otorgan bonificadores positivos, mientras que la lluvia, el viento o temperaturas extremas aplican penalizaciones.
* **Calidad del Aire (AQI):** Respirar aire limpio bonifica la generación de tropas, mientras que los niveles altos de contaminación la reducen severamente.
* *Fórmula de Dataflow:* `Ejércitos = (Pasos / 500) * Factor Clima * Factor Aire`

**2. Sistema Anti-Trampas (Dataflow Juez):**
Para evitar que los usuarios generen tropas yendo en coche o usando bots, el pipeline de Dataflow vigila cada movimiento con tres reglas estrictas:
* **Radar de velocidad:** Si la distancia entre dos puntos GPS refleja una velocidad superior a **15 km/h**, el evento se marca como trampa y se descarta automáticamente.
* **Límite de Pasos Diarios:** Solo se contabilizan un máximo de **30.000 pasos al día** por jugador (equivalente a casi una maratón).
* **Límite de Tropas:** Ningún jugador puede generar más de **50 ejércitos** en un periodo de 24 horas.

**3. Conquista y Tablero:**
* **Adyacencia:** Los jugadores solo pueden atacar o fortificar los barrios de Valencia que compartan frontera directa con sus territorios actuales.
* **Coste de Acción:** Atacar un barrio enemigo o mover tropas consume *Power Points* (Pool). Si el jugador se queda sin puntos, debe volver a salir a caminar para recargar su capacidad de acción.
* **Desgaste:** Atacar reduce temporalmente el nivel de defensa de la zona desde la que se lanza el ataque.

---

## 4. Flujo de datos

Explicamos como funcionan los dos flujos de datos 
- Flujo 1: pasos y multiplicadores + pipeline dataflow + inserts a las tablas
- Flujo 2: Como el usuario selecciona ejercitos y los mete en las tablas

---

## 5. Estructura de tablas — Firestore & BigQuery

Explicar las 4 tablas, para qué sirve cada una, estructura de datos. Por qué escogemos Firestore y BigQuery.

---

## 6. Arranque en local
El arranque local supone levantar la arquitectura mediante contenedores de docker locales y scripts de python en nuestro propio ordenador. Para ello usamos imagenes oficiales de Pub/Sub y Firestore para simular en local esos servicios de GCP. Mediante el despliegue en local somos capaces de testear la arquitectura y desarrollar el proyecto de forma cómoda y sin levantar recursos reales en el proyecto de GCP que suponen un coste. La estructura del repositorio está diseñada para poder levantarse en local o en nube indistintamente. 

Pasos para arrancar la arquitectura en local: 

**Terminal 1 — Docker**

Levantamos los contenedores de Pub/Sub, Firestore, APIs y frontend:
```bash
docker compose up -d --build
```
**Terminal 2 — Crear topics en el emulador (una sola vez)**

El contenedor de Pub/Sub está vacío, tenemos que crear los tópicos y suscripciones de manera manual:
```bash
export PUBSUB_EMULATOR_HOST="localhost:8085"
pip install google-cloud-pubsub
python scripts/setup_local_pubsub.py
```
**Terminal 3 — Pipeline Apache Beam (queda corriendo)**

Apache Beam es un script que se ejecuta en nuestro ordenador (el pipeline), tenemos que levantarlo a mano:
```bash
export PUBSUB_EMULATOR_HOST="localhost:8085"
export FIRESTORE_EMULATOR_HOST="localhost:8200"
pip install -r pipelines/requirements.txt
python pipelines/cloudrisk_unified.py \
    --runner=DirectRunner \
    --project=cloudrisk-local \
    --player_sub=projects/cloudrisk-local/subscriptions/player-movements-sub \
    --weather_sub=projects/cloudrisk-local/subscriptions/weather-sub \
    --airq_sub=projects/cloudrisk-local/subscriptions/air-quality-sub \
    --local --streaming
```
**Terminal 4 — Walker / simulador de pasos (genera datos)**

Ejecutamos el generador de pasos: 
```bash
export PUBSUB_EMULATOR_HOST="localhost:8085"
export PUBSUB_PROJECT="cloudrisk-local"
pip install -r data_generator/requirements.txt
python data_generator/juego_caminante.py --moves 50 --pause 0.5
```
---

## 7. Despliegue a GCP

### ¿Es esto 100 % serverless como pide Javier?

Sí — el stack está alineado con el repo de referencia de clase ([jabrio/Serverless_EDEM_2026](https://github.com/jabrio/Serverless_EDEM_2026)). Nada de Compute Engine, ni GKE, ni VMs que tengamos que mantener nosotros. Los servicios son todos gestionados por Google: Cloud Run, Dataflow, Pub/Sub, Firestore, BigQuery, Cloud Scheduler, Secret Manager, Artifact Registry, Cloud Storage.

Hay dos matices técnicos que conviene dejar por escrito para que no parezcan descuidos:

1. **`air-ingestor` y `weather-ingestor` tienen `min_instance_count = 1`** ([08_cloud_run.tf](infrastructure/terraform/08_cloud_run.tf)). Cloud Run "puro" escala a cero, pero estos dos servicios hacen polling cada 30s a OpenWeather — si escalaran a cero dejarían de pollear. Siguen siendo serverless (pagamos por uso, no gestionamos la VM), pero con 1 instancia tibia permanente.
2. **Dataflow streaming mantiene workers 24/7** ([12_dataflow.tf](infrastructure/terraform/12_dataflow.tf)). Un job streaming por definición no escala a cero: los workers los gestiona Google con autoscaling de 1 a 3, pero siempre hay al menos 1. Es el mismo patrón que el `realtime_recommendation_engine` del repo del profe.

Los demás servicios (`cloudrisk-api`, `cloudrisk-web`) sí escalan a cero cuando nadie los usa. `walker` y `steps-fetcher` son Cloud Run **Jobs**, así que ni siquiera están corriendo salvo cuando los dispara el Scheduler.

La consigna del profe es literal: *"The infrastructure must be managed as a Terraform project, allowing the entire architecture to be deployed seamlessly with a single terraform apply command"*. Eso es lo que hemos montado — el apartado 7.3 de abajo.

---

### Cómo se despliega

Todo el despliegue va con Terraform. La idea es: `terraform init`, `terraform plan`, `terraform apply` y ya. No hay pasos "manuales" raros en medio — los builds de Docker y el flex template de Dataflow los dispara el propio Terraform (los metí dentro de `null_resource` en [infrastructure/terraform/13_docker_builds.tf](infrastructure/terraform/13_docker_builds.tf)).

Lo único que Terraform NO puede hacer por sí solo es lo previo: loguearte en GCP, crear el bucket donde vive su propio state, y autenticar Docker contra Artifact Registry. Eso lo hace `infrastructure/deploy.sh` en 4 comandos — una sola vez por ordenador.

Antes de empezar hace falta tener `gcloud`, `docker` y `terraform` instalados. Y Docker corriendo (Docker Desktop abierto en Mac/Windows).

### 7.1 — Bootstrap (solo una vez por máquina)

Este script hace lo que Terraform no puede hacer por sí mismo: login, bucket de state, auth de Docker. Detalle de qué hace por dentro al final de esta sección.

```
bash infrastructure/deploy.sh cloudrisk-492619
```

### 7.2 — Rellenar `terraform.tfvars`

Los secretos del proyecto (JWT para login y token del scheduler) los necesita Terraform pero NO queremos que se suban a GitHub. Por eso están en `terraform.tfvars`, que está gitignored.

Copia el ejemplo y genera los dos secretos:
```
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Los 2 valores que imprime los pegas en `terraform.tfvars` como `jwt_secret` y `scheduler_secret`.

### 7.3 — Terraform init / plan / apply

Desde la carpeta de Terraform:
```
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

`terraform apply` tarda un rato (unos 15-20 min la primera vez) porque construye y sube las 6 imágenes Docker + el flex template de Dataflow + todos los recursos de GCP. Al final imprime las URLs públicas del backend y del frontend.

### 7.4 — Paso manual: key de OpenWeatherMap

Este es el único paso que no se puede automatizar. La key la da OpenWeatherMap después de registrarte en su web, así que hay que meterla a mano después del `terraform apply`. Mientras no lo hagas, los ingestors de aire y clima arrancan pero no traen datos reales.

```
echo -n 'TU_KEY_DE_OPENWEATHER' | gcloud secrets versions add openweather-api-key --data-file=-
```

Cloud Run la recoge automáticamente (lee `version = "latest"`).

### ¿Qué hace `infrastructure/deploy.sh` por dentro?

Las 4 cosas que Terraform no puede hacer por sí mismo:
1. **`gcloud auth login`** + **`application-default login`** — te loguea en GCP (se abre el navegador).
2. **Crea el bucket GCS de tfstate** (`<project-id>-tfstate`) con versionado activado — es donde Terraform guarda su contabilidad. Si lo borras, Terraform se vuelve loco.
3. **Habilita las 2 APIs mínimas** (Artifact Registry + Cloud Resource Manager) — las demás las habilita Terraform en `01_apis.tf`.
4. **`gcloud auth configure-docker`** — para que `docker push` contra Artifact Registry funcione sin pedir password.

Si lo quieres cambiar o entender mejor está en [infrastructure/deploy.sh](infrastructure/deploy.sh) — son unas 80 líneas bien comentadas.

### Qué se despliega
- **Firestore** — base de datos del juego (zonas, jugadores, batallas), con PITR de 7 días
- **Pub/Sub** — 3 colas de mensajes (pasos, clima, aire) con sus DLQ
- **BigQuery** — dataset `cloudrisk` para la analítica
- **Cloud Run** — 4 servicios (api, web, air-ingestor, weather-ingestor) + 2 jobs (walker, steps-fetcher)
- **Dataflow** — el pipeline unificado que convierte pasos en ejércitos
- **Cloud Scheduler** — los crons diarios (decay, batallas, ingesta de pasos)

---

## 8. Arquitectura detallada

La sección 2 da la foto general. Esta sección desgrana **qué corre dónde, quién habla con quién y por dónde pasan los datos** a partir de lo que realmente hay en el repo (código + Terraform).

### 8.1 — Diagrama de componentes

> Reemplaza este bloque por una imagen (`![arquitectura](ruta/imagen.png)`) cuando la tengas. Mientras tanto, aquí va el esquema en ASCII que resume cómo fluye todo:

```
┌─────────────────────────── FUENTES (Cloud Run) ──────────────────────────┐
│                                                                            │
│   ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐   ┌──────────┐│
│   │   walker     │   │  steps-fetcher   │   │ air-ingestor │   │ weather- ││
│   │   (Job)      │   │   (Job, 03:00)   │   │ (min=1, 30s) │   │ ingestor ││
│   │ 4 bots sim.  │   │  ← random_tracker│   │ ← OWM aire   │   │ ← OWM    ││
│   └──────┬───────┘   └────────┬─────────┘   └──────┬───────┘   └────┬─────┘│
└──────────┼────────────────────┼────────────────────┼────────────────┼─────┘
           │                    │                    │                │
           ▼                    ▼                    ▼                ▼
   ╔══════════════════════════════╗   ╔══════════════╗   ╔═════════════╗
   ║    player-movements  (topic) ║   ║ air-quality  ║   ║  weather    ║
   ╚──────────────┬───────────────╝   ╚──────┬───────╝   ╚──────┬──────╝
                  │                          │                  │
                  └────────────┬─────────────┴──────────────────┘
                               ▼
                   ┌─────────────────────────┐
                   │   Dataflow streaming    │
                   │   cloudrisk-unified     │   ← stateful:
                   │  (Flex Template, 1-3    │       last_location,
                   │   workers, 24/7)        │       armies_today,
                   │                         │       steps_today,
                   │  - parse + validate     │       timer 24h UTC
                   │  - anti-trampa (speed)  │
                   │  - haversine distance   │
                   │  - env_multiplier       │
                   │  - caps diarios         │
                   └──────┬───────────┬──────┘
                          │           │
              ┌───────────┘           └────────────┐
              ▼                                    ▼
     ┌────────────────────┐              ┌──────────────────────┐
     │    Firestore       │              │      BigQuery        │
     │  (región eur3)     │              │   (dataset cloudrisk)│
     │                    │              │                      │
     │  users, zones,     │              │  player_scoring_     │
     │  clans, battles,   │              │    events            │
     │  user_balance ◄──┐ │              │  environmental_      │
     │  location_balance│ │              │    factors           │
     └─────────┬────────┼─┘              │  dead_letter         │
               │        │                 └──────────┬───────────┘
               │        │                            │
               ▼        │                            ▼
     ┌────────────────────┐                 ┌──────────────────┐
     │   cloudrisk-api    │◄────────────────│  (lectura de     │
     │   FastAPI + WS     │                 │   analíticas)    │
     │   (Cloud Run, 0-10)│                 └──────────────────┘
     └────────┬──────────┬┘
              │          │                  ┌──────────────────┐
              │          └─────── llamada ──┤ Cloud Scheduler  │
              │                   horaria   │ - resolve-battles│
              │                             │ - steps-fetcher  │
              │                             └──────────────────┘
              ▼
     ┌────────────────────┐          ┌──────────────┐
     │   cloudrisk-web    │◄────────►│   Usuario    │
     │   React + MapLibre │          │   (navegador)│
     │   (Cloud Run, 0-5) │          └──────────────┘
     └────────────────────┘
```

### 8.2 — Inventario de componentes

**Cloud Run Services** ([08_cloud_run.tf](infrastructure/terraform/08_cloud_run.tf))

| Servicio | Fuente | Escalado | Rol |
|---|---|---|---|
| `cloudrisk-api` | [backend/](backend/) | 0–10 | FastAPI: 13 routers REST + WebSocket |
| `cloudrisk-web` | [frontend/](frontend/) | 0–5 | React + Vite + MapLibre 3D |
| `cloudrisk-air-ingestor` | [weather_airq/calidad_aire.py](weather_airq/calidad_aire.py) | 1 fijo | Poll de calidad del aire cada 30s → Pub/Sub |
| `cloudrisk-weather-ingestor` | [weather_airq/clima.py](weather_airq/clima.py) | 1 fijo | Poll de clima cada 30s → Pub/Sub |

**Cloud Run Jobs** ([08_cloud_run.tf:253](infrastructure/terraform/08_cloud_run.tf#L253), [11_steps_ingestor.tf:48](infrastructure/terraform/11_steps_ingestor.tf#L48))

| Job | Fuente | Disparo | Rol |
|---|---|---|---|
| `cloudrisk-walker` | [data_generator/juego_caminante.py](data_generator/juego_caminante.py) | Manual / Scheduler | Simula 4 bots caminando por Valencia |
| `cloudrisk-steps-fetcher` | [steps_ingestor/recolector_pasos_diario.py](steps_ingestor/recolector_pasos_diario.py) | Cron diario 03:00 UTC | Descarga pasos reales del repo `random_tracker` |

**Dataflow** ([12_dataflow.tf](infrastructure/terraform/12_dataflow.tf), [pipelines/cloudrisk_unified.py](pipelines/cloudrisk_unified.py))

Flex Template en streaming, **stateful**. Consume las 3 suscripciones de Pub/Sub y escribe en Firestore + BigQuery. Detalles en 8.3.

**Pub/Sub** ([02_pubsub.tf](infrastructure/terraform/02_pubsub.tf)) — 3 topics con su DLQ:

| Topic | Productor | Subscripción | Consumidor |
|---|---|---|---|
| `player-movements` | walker, steps-fetcher | `player-movements-sub` | Dataflow |
| `air-quality` | air-ingestor | `air-quality-sub` | Dataflow |
| `weather` | weather-ingestor | `weather-sub` | Dataflow |

**Firestore** ([03_firestore.tf](infrastructure/terraform/03_firestore.tf)) — `FIRESTORE_NATIVE`, región `eur3`, PITR 7 días, delete protection. Colecciones: `users`, `zones` (87 barrios de Valencia), `clans`, `battles`, `step_logs`, `user_balance` ⟵ _contrato de equipo, escrito por Dataflow_, `location_balance` ⟵ _contrato de equipo, escrito por backend_.

**BigQuery** ([04_bigquery.tf](infrastructure/terraform/04_bigquery.tf)) — dataset `cloudrisk` (EU multi-region):
- `player_scoring_events` — evento-por-evento del pipeline (particionado por día, clusterizado por `player_id`).
- `environmental_factors` — lecturas de aire/clima con su multiplicador (particionado por día).
- `dead_letter` — eventos rechazados con motivo y payload original.

**Cloud Scheduler** ([09_scheduler.tf](infrastructure/terraform/09_scheduler.tf), [11_steps_ingestor.tf:102](infrastructure/terraform/11_steps_ingestor.tf#L102))

| Cron | Horario | Dispara |
|---|---|---|
| `cloudrisk-resolve-battles` | `0 * * * *` (cada hora) | `POST /api/v1/battles/resolve-expired` en el backend |
| `cloudrisk-steps-fetcher-daily` | `0 3 * * *` | Cloud Run Job `steps-fetcher` |

**Secret Manager** ([06_secrets.tf](infrastructure/terraform/06_secrets.tf)) — `cloudrisk-jwt-secret`, `openweather-api-key`, `scheduler-secret`.

**Service Accounts** ([07_iam.tf](infrastructure/terraform/07_iam.tf)) — 6 SA con mínimo privilegio: `cloudrisk-api`, `cloudrisk-ingestor`, `cloudrisk-walker`, `cloudrisk-steps-ingestor`, `cloudrisk-dataflow`, `cloudrisk-scheduler`.

**Artifact Registry** ([05_artifact_registry.tf](infrastructure/terraform/05_artifact_registry.tf)) — repo `cloudrisk` en `europe-west1-docker.pkg.dev` con 7 imágenes: `api`, `frontend`, `walker`, `air-ingestor`, `weather-ingestor`, `steps-ingestor`, `dataflow-unified`.

### 8.3 — Flujos de datos

**Flujo A · Pasos → ejércitos** _(el camino principal del juego)_

1. `walker` o `steps-fetcher` publica `{player_id, lat, lng, steps, ts}` en `player-movements`.
2. Dataflow consume con una `ScoringDoFn` **stateful** ([pipelines/cloudrisk_unified.py](pipelines/cloudrisk_unified.py)):
   - `ReadModifyWriteStateSpec` guarda la última posición del jugador → calcula distancia haversine.
   - **Anti-trampa**: si `speed_kmh > MAX_SPEED_KMH` (15) → DLQ.
   - Lee `env_multiplier` (aire × clima, rango 0.6–1.5) desde side input.
   - `armies = (steps_delta × env_multiplier) / POWER_PER_STEPS`.
   - `CombiningValueStateSpec` acumula `armies_today` y `steps_today`. Si superan los caps → se capa y marca `capped=true`.
   - `TimerSpec` (REAL_TIME) resetea los contadores a las 00:00 UTC.
3. Escritura doble: **Firestore** (`user_balance` con `Increment`) + **BigQuery** (`player_scoring_events`).
4. El frontend ve el nuevo balance al consultar `/api/v1/users/me`.

**Flujo B · Acciones del usuario**

React llama a endpoints del FastAPI ([backend/cloudrisk_api/main.py](backend/cloudrisk_api/main.py)) con JWT Bearer. Endpoints clave:

| Endpoint | Fichero | Qué hace |
|---|---|---|
| `POST /users/register`, `/login` | [endpoints/usuarios.py](backend/cloudrisk_api/endpoints/usuarios.py) | Alta + JWT (7 días) |
| `GET /zones/` | [endpoints/zonas.py](backend/cloudrisk_api/endpoints/zonas.py) | Lista 87 barrios + adyacencias |
| `POST /armies/place`, `/fortify` | [endpoints/ejercitos.py](backend/cloudrisk_api/endpoints/ejercitos.py) | Despliega tropas en zonas |
| `POST /battles/`, `/{id}/resolve` | [endpoints/batallas.py](backend/cloudrisk_api/endpoints/batallas.py) | Combate tipo Risk con dados |
| `GET /multiplicadores/` | [endpoints/multiplicadores.py](backend/cloudrisk_api/endpoints/multiplicadores.py) | Multiplicador aire×clima actual |
| `GET /analiticas/*` | [endpoints/analiticas.py](backend/cloudrisk_api/endpoints/analiticas.py) | Consultas a BigQuery (top pasos, días lluviosos, mala calidad del aire…) |

El backend escribe en Firestore (dato caliente) y consulta BigQuery (histórico/analítica). Cloud Scheduler dispara endpoints internos con header `X-Scheduler-Token`.

**Flujo C · Multiplicadores ambientales**

`air-ingestor` y `weather-ingestor` son _polling loops_ en Cloud Run (por eso `min_instance_count = 1`). Cada 30s llaman a OpenWeatherMap, calculan un multiplicador en [0.6, 1.5], y publican. Dataflow los fusiona como side input y los escribe en `environmental_factors` de BigQuery (auditoría + gráficas).

### 8.4 — Parámetros del juego ([variables.tf](infrastructure/terraform/variables.tf), [configuracion.py](backend/cloudrisk_api/configuracion.py))

| Parámetro | Default | Qué controla |
|---|---|---|
| `POWER_PER_STEPS` | 500 | Pasos necesarios para 1 ejército |
| `DAILY_ARMY_CAP` | 50 | Máx. ejércitos ganables al día |
| `DAILY_STEPS_CAP` | 30 000 | Máx. pasos contabilizados al día |
| `MAX_SPEED_KMH` | 15 | Umbral anti-trampa |
| `STARTING_ARMIES_POOL` | 30 | Tropas iniciales por jugador |
| `INITIAL_ARMIES_PER_ZONE` | 2 | Tropas por zona al setup |
| Rango multiplicador | [0.6, 1.5] | Aire × clima modulan la ganancia |

### 8.5 — Entrada a Terraform ([infrastructure/terraform/](infrastructure/terraform/))

Archivos numerados para leerse en orden. Cada uno tiene un rol único:

```
01_apis.tf               → habilita APIs de GCP
02_pubsub.tf             → topics + subscripciones
03_firestore.tf          → DB del juego
04_bigquery.tf           → dataset + 3 tablas
05_artifact_registry.tf  → registry Docker
06_secrets.tf            → 3 secretos
07_iam.tf                → 6 SA con roles mínimos
08_cloud_run.tf          → 4 servicios + 1 job
09_scheduler.tf          → cron horario de batallas
10_demo_seed.tf          → datos de demo
11_steps_ingestor.tf     → job diario de pasos reales
12_dataflow.tf           → pipeline streaming (Flex Template)
13_docker_builds.tf      → builds de las 7 imágenes (null_resource)
```

