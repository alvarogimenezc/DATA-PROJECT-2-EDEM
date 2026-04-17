# dashboard/

## 🎯 Qué hace este directorio

Es el **dashboard de KPIs y analítica** de CloudRISK. Una app web hecha con **Streamlit** que lee métricas agregadas y las pinta como gráficas, tablas y big numbers:

- Usuarios únicos, pasos totales, zonas conquistadas, batallas por día.
- Factores ambientales (aire, tiempo) que han entrado por los topics de Dataflow.
- Vista "en vivo" del progreso de la partida.

Es distinto del `frontend/`: el frontend es el **juego** (mapa interactivo, clanes, conquistas). El dashboard es el **mirador** para ver qué pasa en agregado — útil en la demo final para enseñar que los datos fluyen de verdad por BigQuery.

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **Python 3.12** | Streamlit vive en Python. Nos permite escribir dashboard + consultas BigQuery en un solo archivo sin frontend-backend separados. |
| **Streamlit** | Framework "data-app" pensado para hacer dashboards en decenas de líneas. Tiene widgets, layout, caching... todo sin JS. Ideal cuando el equipo de datos (Noelia, Martha) quiere iterar rápido. |
| **google-cloud-bigquery + pandas** | BigQuery es donde Dataflow deja las métricas agregadas. `pandas` convierte la query a DataFrame y Streamlit lo pinta. |
| **Cloud Run** | Mismo runtime que el resto de servicios: un contenedor escuchando en `:8080`. Streamlit se adapta con `STREAMLIT_SERVER_PORT=8080`. |

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `main.py` | Toda la app: layout, KPIs, consultas BigQuery, fallback a JSONL local si `METRICS_SOURCE=local`. |
| `Dockerfile` | Imagen `python:3.12-slim`, usuario no-root `app`, `CMD streamlit run main.py` escuchando en `:8080`. |
| `requirements.txt` | `streamlit`, `pandas`, `google-cloud-bigquery`, `db-dtypes`, `pyarrow`, `requests`. |

## 🔗 Cómo se conecta con el resto del proyecto

```
Dataflow (pipeline Noelia+Martha)  ──▶  BigQuery: cloudrisk_metrics.step_events
                                                  cloudrisk.environmental_factors
                                                        │
                                                        ▼
                                                 dashboard/main.py
                                                        │
                                                        ▼
                                             Cloud Run service: cloudrisk-dashboard
                                                        │
                                                        ▼
                                          URL pública (la sirve Terraform en outputs.tf)
```

- Lee de **BigQuery** (datasets `cloudrisk_metrics` y `cloudrisk`) por defecto.
- Si `METRICS_SOURCE=local`, lee ficheros `.jsonl` desde `LOCAL_METRICS_DIR` (útil en `docker compose` sin GCP).
- Opcionalmente consulta el backend (`BACKEND_URL`) para enriquecer con datos de partida en tiempo real.

## 🚀 Cómo ejecutarlo

```bash
# Local contra BigQuery real (requiere gcloud auth application-default login)
cd dashboard
pip install -r requirements.txt
PROJECT_ID=cloudrisk-492619 streamlit run main.py

# Local con docker compose (modo local-metrics, sin GCP)
docker compose up dashboard

# Build + run manual con Docker
docker build -t cloudrisk-dashboard ./dashboard
docker run --rm -p 8080:8080 -e PROJECT_ID=cloudrisk-492619 cloudrisk-dashboard

# Deploy manual a Cloud Run (usa el script del equipo)
bash CICD/desplegar_manual.sh dashboard
```

Variables de entorno:

| Var | Default | Para qué |
|---|---|---|
| `PROJECT_ID` | `cloudrisk-local` | Proyecto GCP de BigQuery. |
| `BIGQUERY_DATASET` | `cloudrisk_metrics` | Dataset con `step_events`, batallas, etc. |
| `ENV_DATASET` / `ENV_TABLE` | `cloudrisk` / `environmental_factors` | Tabla ambiental. |
| `METRICS_SOURCE` | `bigquery` | Pon `local` para leer JSONL offline. |
| `BACKEND_URL` | `http://localhost:8080` | URL del backend para datos en vivo. |
