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

## 6. Arranque rápido en local

Fran explica que es esto y como funciona, con sus palabras. Solo explicamos 1 forma de arrancar, la mas sencilla:

---

### ¿Qué es el arranque en local?

El arranque en local es cuando nosotros levantamos el proyecto que llamamos "CloudRisk" sin tocar ninguna opcion de Google Cloud Platform, en este caso en vez de conectarnos a FireStore o Pub/Sub reales, lo hacemos en emuladores oficiales de Google dentro de nuestros contenedores de Docker.

¿Por que? ... Porque asi cualquierra del equipo puede arrancar el proyecto sin la necesidad de tener un cuenta de google cloud, ni configurar nada, ni pagar nada.

---

## ¿De donde sale cada cosa que tenemos en local?

### 🔹 Frontend

- Servicio de frontend sale del puerto **3000** que es el puerto que tenemos configurado en el docker compose para el servicio de frontend

#### ¿Cómo se construyó y qué tecnologías se usaron?

React + Vite, el framework que hemos escogido para el desarrollo del frontend de CloudRisk. Es un framework de desarrollo web que nos permite crear aplicaciones web de manera rápida y sencilla, con una gran cantidad de funcionalidades y herramientas integradas. Vite es un framework de desarrollo web moderno que se basa en la idea de "desarrollo rápido", lo que significa que nos permite desarrollar aplicaciones web de manera rápida y eficiente, sin tener que preocuparnos por la configuración y el rendimiento.

#### ¿Qué hay aquí?

- (Mapa, login, /analytics)

---

### 🔹 API

- Servicio de API sale del puerto **8080** que es el puerto que tenemos configurado en el docker compose para el servicio de API

#### ¿Con qué tecnologías se construyó?

El servicio de API de CloudRisk se construyó utilizando Python y FastAPI. FastAPI es un framework web moderno y rápido para construir APIs con Python. Es fácil de usar, tiene una gran cantidad de funcionalidades integradas y es muy eficiente en términos de rendimiento. Además, FastAPI es compatible con OpenAPI, lo que nos permite generar documentación automática para nuestra API.

#### ¿Qué hay aquí?

- (Endpoints para el login, el estado del mapa, y el endpoint de analytics)

---

### 🔹 Firestore Emulator

- Firestore emulator sale del puerto **8200** que es el puerto que tenemos configurado en el docker compose para el servicio de Firestore emulator

Base de datos en tiempo real (FALSA) que nos permite hacer? Nos permite almacenar y sincronizar datos entre los clientes y el servidor en tiempo real. En nuestro caso, lo usamos para almacenar el estado del juego, las tropas desplegadas, los movimientos de los jugadores, etc. Es una base de datos NoSQL que nos permite trabajar con documentos y colecciones, lo que nos da mucha flexibilidad a la hora de modelar nuestros datos.

---

### 🔹 Pub/Sub Emulator

- Pub/Sub emulator sale del puerto **8085** que es el puerto que tenemos configurado en el docker compose para el servicio de Pub/Sub emulator

Sistema de mensajería en tiempo real (FALSO) que nos permite enviar y recibir mensajes entre diferentes partes de nuestra aplicación. En nuestro caso, lo usamos para enviar los pasos que da cada jugador desde el frontend al backend, y para enviar los multiplicadores desde el backend al frontend. Es un sistema de mensajería basado en el modelo de publicación-suscripción, lo que significa que los productores de mensajes (publicadores) envían mensajes a un tema, y los consumidores de mensajes (suscriptores) reciben mensajes de ese tema o topic.

---

## Desplegar en local

1. Crear un `.env`  
2. Ejecutar:

```bash
docker compose up -d -- build
```

### Servicios disponibles

- **Frontend (incl. /analytics)** → http://localhost:3000  
- **API + Swagger** → http://localhost:8080/api/v1/docs  
- **Firestore emulator** → localhost:8200  
- **Pub/Sub emulator** → localhost:8085  
- **Dataflow** → localhost:8080 (endpoint de Dataflow en local)


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