# consumer/

## 🎯 Qué hace este directorio

Es un **consumer de Pub/Sub para debug**. Se suscribe al topic `player-movements` (vía la subscription `player-movements-sub`) usando el modelo PULL y escribe en `stdout` cada mensaje que llega.

No procesa nada — no guarda en BigQuery, no actualiza Firestore. Para eso están Dataflow y el `steps_ingestor/`. Este servicio existe porque en dev queremos ver **en tiempo real** lo que está publicando el walker o el frontend, sin tener que abrir la consola web de GCP ni tirar de `gcloud pubsub subscriptions pull` a mano.

Básicamente: `docker compose up consumer` → ves los pasos del juego fluir por terminal.

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **Python 3.12** | Es el lenguaje por defecto del equipo (Fran, Álvaro, Noelia, Martha, Ricardo). El SDK oficial `google-cloud-pubsub` es maduro y hace PULL con `StreamingPullFuture` en tres líneas. |
| **google-cloud-pubsub 2.23.0** | Cliente oficial. Lo pinamos a esa versión porque es la que valida el contrato del topic del equipo. |
| **PULL** (no PUSH) | El consumer decide el ritmo. No hay endpoint HTTP que exponer, ni sorpresas de deadletter si el contenedor reinicia. Para una herramienta de debug que corre en el portátil o en Cloud Run con baja concurrencia, PULL es la opción simple. |

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `main.py` | Abre un `SubscriberClient`, se registra a `player-movements-sub` y logea cada mensaje (player_id, lat, lon, speed). Maneja SIGINT/SIGTERM limpiamente. |
| `Dockerfile` | Imagen `python:3.12-slim`, `pip install -r requirements.txt`, `CMD python -u main.py` (stdout sin buffering para que Cloud Run capture logs en vivo). |
| `requirements.txt` | Solo `google-cloud-pubsub==2.23.0`. Nada más. |

## 🔗 Cómo se conecta con el resto del proyecto

```
data_generator/ (walker, bots)  ─┐
frontend/ (posición del jugador) ─┼─▶  Pub/Sub topic: player-movements
steps_ingestor/ (tracker)        ─┘                  │
                                                     ▼
                                        player-movements-sub
                                                     │
                                                     ▼
                                             consumer/ (este)  ─▶ stdout / Cloud Logging
```

- El **topic** y la **subscription** los crea Terraform (`02_pubsub.tf`).
- El **publisher** principal es `data_generator/` (walker sintético y bots de IA).
- Pipeline real de procesado: **Dataflow** (Noelia + Martha) lee el mismo topic y escribe en BigQuery. Este consumer **no reemplaza** a Dataflow, solo ayuda a depurar.

## 🚀 Cómo ejecutarlo

```bash
# Local con docker compose (usa emulador de Pub/Sub por defecto)
docker compose up consumer

# Local apuntando a Pub/Sub real en GCP
gcloud auth application-default login
PUBSUB_PROJECT=cloudrisk-492619 \
SUBSCRIPTION=player-movements-sub \
python consumer/main.py

# Build + run manual con Docker
docker build -t cloudrisk-consumer ./consumer
docker run --rm -e PUBSUB_PROJECT=cloudrisk-492619 cloudrisk-consumer
```

Variables de entorno:

| Var | Default | Para qué |
|---|---|---|
| `PUBSUB_PROJECT` | `cloudrisk-492619` | Proyecto GCP donde vive el topic. |
| `SUBSCRIPTION` | `player-movements-sub` | Nombre de la subscription a consumir. |
