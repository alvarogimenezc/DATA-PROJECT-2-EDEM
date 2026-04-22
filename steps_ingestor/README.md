# 📥 CloudRISK - Ingestor de Pasos (Step Ingestor)

Este componente actúa como el puente entre el mundo físico (simulado a través de trackers) y el entorno en la nube de **CloudRISK**. Su única responsabilidad es descargar archivos de telemetría y publicarlos en Google Cloud Pub/Sub para que el pipeline unificado (Dataflow) los procese.

> **Evolución Arquitectónica:** En versiones anteriores, este módulo también realizaba el cálculo de puntuaciones (scoring). Dicha lógica ha sido delegada completamente al pipeline de streaming de Dataflow (`pipelines/cloudrisk_unified.py`) para garantizar un procesamiento unificado y con estado.

## 🚀 Funciones Principales

* **Extracción Remota:** Descarga un archivo JSON diario con coordenadas GPS, velocidad y conteo de pasos desde un repositorio público externo.
* **Resolución de Identidades:** Utiliza un archivo de mapeo (`random_tracker_mapping.json`) para vincular los nombres de usuario del tracker externo con los `player_id` internos de Firestore.
* **Control de Idempotencia:** Registra marcadores diarios en Firestore (`step_ingests/`) para evitar el doble procesamiento en caso de ejecuciones duplicadas o reintentos.
* **Publicación en Pub/Sub:** Inyecta cada movimiento individual en el topic configurado (por defecto, `player-movements`).

## 🛠️ Tecnologías

* **Lenguaje:** Python 3.12.
* **Librerías Clave:** `google-cloud-pubsub` (Mensajería), `google-cloud-firestore` (Control de estado/idempotencia).
* **Infraestructura:** Desplegado como un **Cloud Run Job** programado.

## ⚙️ Variables de Entorno y Argumentos

El script `recolector_pasos_diario.py` soporta ejecución por argumentos CLI:

| Parámetro | Descripción |
| :--- | :--- |
| `--project` | ID del proyecto en GCP (obliga a establecerlo en despliegue). |
| `--topic` | Topic de Pub/Sub destino (por defecto: `player-movements`). |
| `--date` | Fecha a descargar en formato `YYYY-MM-DD` (por defecto: HOY). |
| `--force` | Ignora el control de idempotencia y vuelve a procesar el día. |
| `--dry-run` | Procesa y mapea los datos imprimiéndolos por consola, sin publicar en Pub/Sub ni escribir en Firestore. |
| `--local-file` | Omite la descarga externa y lee directamente de un JSON local. |

## 📦 Cómo Ejecutarlo

**En Local (Modo Pruebas / Offline):**
Ideal para probar el parseo usando el archivo *mock* generado en la carpeta `data/`.
```bash
pip install -r requirements.txt
python recolector_pasos_diario.py \
  --project cloudrisk-local \
  --local-file ../data/mock_tracker_feed.json \
  --dry-run