# CloudRISK — Serverless Urban Conquest

**Camina Valencia. Cada paso es munición. Conquista los 87 barrios.**

Proyecto 100 % **serverless** sobre Google Cloud Platform. Juego de estrategia geolocalizado tipo *Risk* sobre Valencia, construido como pipeline de datos **100 % serverless** en GCP.

## Índice
  - [1. Qué es CloudRISK]
  - [2. Arquitectura]
  - [3. Reglas del juego]
  - [4. Flujo de datos]
  - [5. Estructura de tablas - Firestores & BigQuery]
  - [6. Arranque rápido en local]
  - [7. Despliegue a GCP]
  - [8. Resultados, aprendizajes y mejoras]

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

Insertamos la imagen resumen dearquitectura - lo hace Álvaro a partir del miro

---

## 3. Reglas del juego

Explicar las reglas del juego

---

## 4. Flujo de datos

Explicamos como funcionan los dos flujos de datos 
- Flujo 1: pasos y multiplicadores + pipeline dataflow + inserts a las tablas
- Flujo 2: Como el usuario selecciona ejercitos y los mete en las tablas


---

## 5. Estructura de tablas - Firestores & BigQuery

Explicar las 4 tablas, para que sirve cada una, estructura de datos. Por que escojemos firestore y bigquery

---

## 6. Arranque rápido en local

Fran explica que es esto y como funciona, con sus palabras. Solo explicamos 1 forma de arrancar, la mas sencilla:

cp .env.example .env
docker compose up --build

Frontend (incl. /analytics) → http://localhost:3000
API + Swagger → http://localhost:8080/api/v1/docs
Firestore emulator → localhost:8200
Pub/Sub emulator → localhost:8085

---

## 7. Despliegue a GCP

Fran explica que es esto y como funciona, con sus palabras. Solo explicamos 1 forma de arrancar, la mas sencilla:
 
*5.1 — Preparar la máquina (una vez)*
gcloud auth login
gcloud auth application-default login
gcloud config set project cloudrisk-492619


*5.2 — Bucket para el state de Terraform (una vez)*
gsutil mb -l europe-west1 gs://cloudrisk-492619-tfstate
gsutil versioning set on gs://cloudrisk-492619-tfstate


*5.3 — Rellenar terraform.tfvars*
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars


*Generar secretos fuertes (cross-platform)*
python -c "import secrets; print('jwt_secret =', repr(secrets.token_hex(32)))"
python -c "import secrets; print('scheduler_secret =', repr(secrets.token_hex(32)))"
Pega ambos en terraform.tfvars

*5.4 — terraform apply*
terraform init
terraform plan
terraform apply
Esto crea:

---

## 8. Resultados, aprendizajes y mejoras