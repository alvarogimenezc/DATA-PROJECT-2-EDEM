# 🤖 CloudRISK - Generadores de Datos y Simuladores (WalkRisk)

Este módulo contiene los scripts de inteligencia artificial y generación de tráfico sintético. Dado que evaluar una arquitectura de Big Data requiere volumen de información, estos simuladores inyectan movimiento físico (GPS) y acciones de juego en el sistema de manera automática.

## 🚀 Funciones Principales

* **Caminantes GPS (`juego_caminante.py`):** Simula a 4 comandantes paseando de forma realista por los 87 barrios de Valencia. Calcula distancias (Haversine) y envía telemetría de pasos a Google Cloud Pub/Sub.
* **Bots de Estrategia (`simulacion_multijugador.py` y `simulacion_rapida_juego.py`):** IA que juega partidas completas contra el backend. Evalúa adyacencias, calcula heurísticas de riesgo, refuerza fronteras y realiza conquistas.
* **Respaldo Local (`recolector_metricas_local.py`):** Un consumidor de Pub/Sub que actúa como plan de contingencia. Descarga los eventos y los guarda en archivos `.jsonl` locales en caso de que el pipeline de Dataflow falle.
* **Setup de Partida (`tabla_reglas_inicio.py`):** Utilidad que arranca el mapa inicial en Firestore distribuyendo ejércitos basados en el histórico de pasos.

## 🛠️ Tecnologías
* **Lenguaje:** Python 3.12.
* **Librerías Clave:** `google-cloud-pubsub` (Mensajería asíncrona), `shapely` (Procesamiento geoespacial), `requests` (Llamadas API).

## ⚙️ Variables de Entorno Clave

| Variable | Descripción |
| :--- | :--- |
| `API_BASE` | URL del backend de CloudRISK (defecto: `http://127.0.0.1:8080`). |
| `PUBSUB_PROJECT` | ID del proyecto de Google Cloud para el envío de telemetría. |
| `PUBSUB_TOPIC_MOVEMENTS` | Topic donde se envían los pasos (defecto: `player-movements`). |
| `CLOUDRISK_LOCAL_METRICS_DIR` | Carpeta de salida para el recolector local (defecto: `/metrics`). |

## 📦 Cómo Ejecutarlo

**1. Simular partidas rápidas (Bots IA):**
Ideal para poblar la base de datos de batallas para los dashboards.
```bash
# Apuntando al backend local
python simulacion_rapida_juego.py

# Modificar número de partidas y movimientos máximos
python simulacion_multijugador.py --runs 5 --max-moves 200

1. **Lanzar caminantes locales (para ver cómo funciona GCP):**
```bash
gcloud auth application-default login
export PUBSUB_PROJECT=cloudrisk-492619
python juego_caminante.py --moves 200 --pause 0.12

2. **Ejecutar el Recolector Local con Docker:**
docker build -t cloudrisk-metrics .
docker run -v $(pwd)/metrics:/metrics -e CLOUDRISK_LOCAL_METRICS_DIR=/metrics cloudrisk-metrics