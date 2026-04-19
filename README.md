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

### ¿Es esto 100 % serverless como pide Javier?

Sí — el stack está alineado con el repo de referencia de clase ([jabrio/Serverless_EDEM_2026](https://github.com/jabrio/Serverless_EDEM_2026)). Nada de Compute Engine, ni GKE, ni VMs que tengamos que mantener nosotros. Los servicios son todos gestionados por Google: Cloud Run, Dataflow, Pub/Sub, Firestore, BigQuery, Cloud Scheduler, Secret Manager, Artifact Registry, Cloud Storage.

Hay dos matices técnicos que conviene dejar por escrito para que no parezcan descuidos:

1. **`air-ingestor` y `weather-ingestor` tienen `min_instance_count = 1`** ([08_cloud_run.tf](infrastructure/terraform/08_cloud_run.tf)). Cloud Run "puro" escala a cero, pero estos dos servicios hacen polling cada 30s a OpenWeather — si escalaran a cero dejarían de pollear. Siguen siendo serverless (pagamos por uso, no gestionamos la VM), pero con 1 instancia tibia permanente.
2. **Dataflow streaming mantiene workers 24/7** ([12_dataflow.tf](infrastructure/terraform/12_dataflow.tf)). Un job streaming por definición no escala a cero: los workers los gestiona Google con autoscaling de 1 a 3, pero siempre hay al menos 1. Es el mismo patrón que el `realtime_recommendation_engine` del repo del profe.

Los demás servicios (`cloudrisk-api`, `cloudrisk-web`, `walker`, `steps-fetcher`) sí escalan a cero cuando nadie los usa.

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

---

### ¿Qué hace `infrastructure/deploy.sh` por dentro?

Las 4 cosas que Terraform no puede hacer por sí mismo:
1. **`gcloud auth login`** + **`application-default login`** — te loguea en GCP (se abre el navegador).
2. **Crea el bucket GCS de tfstate** (`<project-id>-tfstate`) con versionado activado — es donde Terraform guarda su contabilidad. Si lo borras, Terraform se vuelve loco.
3. **Habilita las 2 APIs mínimas** (Artifact Registry + Cloud Resource Manager) — las demás las habilita Terraform en `01_apis.tf`.
4. **`gcloud auth configure-docker`** — para que `docker push` contra Artifact Registry funcione sin pedir password.

Si lo quieres cambiar o entender mejor está en [infrastructure/deploy.sh](infrastructure/deploy.sh) — son 40 líneas bien comentadas.

### Qué se despliega
- **Firestore** — base de datos del juego (zonas, jugadores, batallas), con PITR de 7 días
- **Pub/Sub** — 3 colas de mensajes (pasos, clima, aire) con sus DLQ
- **BigQuery** — dataset `cloudrisk` para la analítica
- **Cloud Run** — 4 servicios (api, web, air-ingestor, weather-ingestor) + 2 jobs (walker, steps-fetcher)
- **Dataflow** — el pipeline unificado que convierte pasos en ejércitos
- **Cloud Scheduler** — los crons diarios (decay, batallas, ingesta de pasos)

---

## 8. Resultados, aprendizajes y mejoras