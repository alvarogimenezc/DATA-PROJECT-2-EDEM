# 🔀 CloudRISK - Pipeline de Datos (Apache Beam / Dataflow)

Este componente es el motor central de procesamiento de **CloudRISK**. Implementa un pipeline de streaming unificado que ingiere eventos del juego y telemetría en tiempo real, los limpia, los enriquece con datos ambientales y los enruta hacia las bases de datos operacionales y analíticas.

## 🚀 Funciones Principales

* **Ingesta Unificada:** Consume simultáneamente de múltiples topics de Pub/Sub (pasos, ubicación, batallas, clima y calidad del aire) dentro del mismo flujo de trabajo.
* **Procesamiento con Estado (Stateful):** Utiliza `State` y `Timers` de Apache Beam para acumular pasos por jugador, aplicando topes diarios (ej. 30.000 pasos máx) y validando velocidades máximas para evitar trampas con el GPS.
* **Enriquecimiento Ambiental (Side Inputs):** Cruza los eventos de batalla en tiempo real con las últimas lecturas de clima y contaminación (AQI) para aplicar multiplicadores de daño.
* **Doble Destino (Sinks):** * Escribe métricas consolidadas en **Google BigQuery** para la analítica y los dashboards.
  * Actualiza el estado operacional de los jugadores (ej. total de pasos) en **Google Firestore** para que el backend lo consuma inmediatamente.

## 🛠️ Tecnologías

* **Framework:** Apache Beam (Python SDK).
* **Runner de Producción:** Google Cloud Dataflow (Streaming mode).
* **Integraciones GCP:** Pub/Sub (Source), BigQuery (Sink analítico), Firestore (Sink operacional).

## ⚙️ Configuración (Pipeline Options)

El pipeline acepta multitud de parámetros. Los más críticos para su despliegue son:

| Parámetro | Descripción |
| :--- | :--- |
| `--project` | ID del proyecto en Google Cloud. |
| `--region` | Región de ejecución (ej. `europe-west1`). |
| `--temp_location` | Bucket de GCS para archivos temporales del worker (`gs://.../temp`). |
| `--input_topic_*` | Topics de entrada para pasos, batallas, clima, etc. |
| `--bq_dataset` | Dataset destino en BigQuery (por defecto: `cloudrisk`). |
| `--daily_steps_cap` | Límite máximo de pasos procesables por jugador al día (defecto: 30000). |
| `--max_speed_kmh` | Límite anti-trampas de velocidad (defecto: 15.0 km/h). |

## 📦 Cómo Ejecutarlo

**En Local (DirectRunner):**
Ideal para pruebas de desarrollo. Consume de Pub/Sub pero procesa en la máquina local.
```bash
pip install -r requirements.txt
python cloudrisk_unified.py \
  --project=tu-project-id \
  --region=europe-west1 \
  --runner=DirectRunner \
  --temp_location=gs://tu-bucket/temp