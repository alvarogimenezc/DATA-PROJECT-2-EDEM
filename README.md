# CloudRISK — Serverless Urban Conquest

**Camina Valencia. Cada paso es munición. Conquista los 87 barrios.**

Proyecto 100 % **serverless** sobre Google Cloud Platform. Juego de estrategia geolocalizado tipo *Risk* sobre Valencia, construido como pipeline de datos **100 % serverless** en GCP.

## Índice
  - 1) Qué es CloudRISK
  - 2) Arquitectura
  - 3) Reglas del juego
  - 4) Flujo de datos
  - 5) Estructura de tablas - Firestores & BigQuery
  - 6) Arranque rápido en local
  - 7) Despliegue a GCP
  - 8) Resultados, aprendizajes y mejoras

Terminar una vez tengamos todas las secciones OK. 

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

Como vemos, se trata de una arquitectura que respeta la filosofía habitual de proyectos de big data : ingesta - transformación - almacenamiento - visualización. 

En nuestro caso, tenemos una ingesta de datos de geolocalización de usuarios, factor de calidad ambiental y calidad del aire. Estos datos entran a dataflow donde se aplica la lógica de negocio y como resultado se insertan los ejercitos equivalentes ganados por el usuario tanto en firestore como en BigQuery. 

Firestore alberga las tablas de estados, en el tenemos la tabla de user_balance y location_balance, que se actualizan conforme avanza la partida con los ejercitos disponibles por usuario y las zonas del mapa con los ejercitos y usuario que las controla. 

La base de datos de BigQuery nos sirve para almacenar datos históricos para métricas y analisis más profundos. 

Por último, el frontend se conecta a la tablas mediante un servidor de FastAPI que sirve como puerta de acceso a las bases de datos. Además, las acciones de los usuarios que puedan hacer en la aplicación también interactuan con las bases de datos mediante este servidor de entrada. 

---

## 3. Reglas del juego

Explicar las reglas del juego, lógica que aplica dataflow de los multiplicadores etc. 

---

## 4. Flujo de datos

Explicamos como funcionan los dos flujos de datos 
- Flujo 1: pasos y multiplicadores + pipeline dataflow + inserts a las tablas
- Flujo 2: Como el usuario selecciona ejercitos y los mete en las tablas

---

## 5. Estructura de tablas - Firestores & BigQuery

Explicar las 4 tablas, para que sirve cada una, estructura de datos. Por que escojemos firestore y bigquery

---

## 6. Arranque en local
El arranque local supone levantar la arquitectura mediante contenedores de docker locales y scripts de python en nuestro propio ordenador. Para ello usamos imagenes oficiales de Pub/Sub y Firestore para simular en local esos servicios de GCP. Mediante el despliegue en local somos capaces de testear la arquitectura y desarrollar el proyecto de forma cómoda y sin levantar recursos reales en el proyecto de GCP que suponen un coste. La estructura del repositorio está diseñada para poder levantarse en local o en nube indistintamente. 

Pasos para arrancar la arquitectura en local: 

**Terminal 1 — Docker**

Levantamos los contenedores de Pub/Sub, IFrestore, APIS y fronted: 
```bash
docker compose up -d --build
```
**Terminal 2 — Crear topics en el emulador (una sola vez)**

El contendor de Pub/Sub está vacío, tenemos que crear los tópicos y suscripciones de manera manual: 
```bash
export PUBSUB_EMULATOR_HOST="localhost:8085"
pip install google-cloud-pubsub
python scripts/setup_local_pubsub.py
```
**Terminal 3 — Pipeline Apache Beam (queda corriendo)**

Apache BEAM es un script que se ejecuta en nuestro ordenador (el pipeline), tenemos que levantarlo a mano: 
```bash
export PUBSUB_EMULATOR_HOST="localhost:8085"
export FIRESTORE_EMULATOR_HOST="localhost:8200"
pip install -r pipelines/requirements.txt
python pipelines/cloudrisk_unified.py `
    --runner=DirectRunner `
    --project=cloudrisk-local `
    --player_sub=projects/cloudrisk-local/subscriptions/player-movements-sub `
    --weather_sub=projects/cloudrisk-local/subscriptions/weather-sub `
    --airq_sub=projects/cloudrisk-local/subscriptions/air-quality-sub `
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

El despliegue tiene **dependencias reales** (el registry tiene que existir antes de pushear imágenes; las imágenes tienen que existir antes de que Cloud Run las arranque; el flex template de Dataflow tiene que estar subido antes de lanzar el job). Por eso lo partimos en **5 fases**, una por comando, en [infrastructure/deploy.sh](infrastructure/deploy.sh). Si una falla, la arreglas y la reejecutas sin tocar las anteriores.

### 7.0 — Una sola vez por máquina
Loguearte en GCP. Los secretos de API se generan solos; no hay nada que rellenar a mano.
```bash
gcloud auth login
gcloud auth application-default login
```

### 7.1 — Fase 1: bootstrap
Habilita las APIs que usamos, crea el bucket de GCS donde vivirá el `tfstate` (versioned, por si algún día hay que hacer rollback) y corre `terraform init` apuntando a ese bucket.
```bash
bash infrastructure/deploy.sh bootstrap cloudrisk-492619
```

### 7.2 — Fase 2: base
`terraform apply` **parcial** (con `-target`) que crea solo 3 cosas: el Artifact Registry `cloudrisk`, los 3 secretos (JWT, scheduler, OpenWeather) y el bucket GCS de Dataflow. Hace falta separarlo de la fase 5 porque no podemos pushear imágenes a un registry que no existe todavía.
```bash
bash infrastructure/deploy.sh base cloudrisk-492619
```

### 7.3 — Fase 3: imágenes
Build + push de las 6 imágenes Docker a Artifact Registry: `api`, `frontend`, `air-ingestor`, `weather-ingestor`, `walker`, `steps-ingestor`. Necesitas Docker corriendo localmente.
```bash
bash infrastructure/deploy.sh images cloudrisk-492619
```

### 7.4 — Fase 4: Dataflow flex template
`gcloud dataflow flex-template build` empaqueta [pipelines/cloudrisk_unified.py](pipelines/cloudrisk_unified.py), lo buildea como imagen Docker y sube un manifiesto JSON al bucket de Dataflow. Sin esto, el job Dataflow no puede arrancar en la fase 5.
```bash
bash infrastructure/deploy.sh flex cloudrisk-492619
```

### 7.5 — Fase 5: apply completo
`terraform apply` completo. Con las imágenes y el flex template ya subidos, Terraform levanta los Cloud Run services (`cloudrisk-api`, `cloudrisk-web`, `air-ingestor`, `weather-ingestor`), los Jobs (`walker`, `steps-fetcher`, `demo-seed`), los crons de Cloud Scheduler y el job de Dataflow. Al acabar imprime las URLs públicas.
```bash
bash infrastructure/deploy.sh apply cloudrisk-492619
```

### 7.6 — Un paso manual que NO puede automatizarse
La key de OpenWeatherMap requiere registro humano en su web. Hasta que no la metas, los ingestors `air-ingestor` y `weather-ingestor` no leen datos reales (arrancan pero fallan en cada llamada a la API):
```bash
echo -n 'TU_OPENWEATHER_KEY' | gcloud secrets versions add openweather-api-key --data-file=-
```
Cloud Run la recoge automáticamente (lee `version = "latest"`).

### Qué crea el despliegue
Detalle en [infrastructure/README.md](infrastructure/README.md). Resumen:
- **Firestore** (Native, `eur3`, PITR de 7 días) — [03_firestore.tf](infrastructure/terraform/03_firestore.tf)
- **Pub/Sub** (3 topics + DLQs) — [02_pubsub.tf](infrastructure/terraform/02_pubsub.tf)
- **BigQuery** (dataset `cloudrisk`, 3 tablas) — [04_bigquery.tf](infrastructure/terraform/04_bigquery.tf)
- **Cloud Run** (2 services + 1 job para backend/frontend + ingestors) — [08_cloud_run.tf](infrastructure/terraform/08_cloud_run.tf)
- **Dataflow** (pipeline unificado stateful) — [12_dataflow.tf](infrastructure/terraform/12_dataflow.tf)
- **Scheduler** (crons de decay y batallas) — [09_scheduler.tf](infrastructure/terraform/09_scheduler.tf)

---

## 8. Resultados, aprendizajes y mejoras