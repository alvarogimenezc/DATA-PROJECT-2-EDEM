# data_generator/

## 🎯 Qué hace este directorio

Es el **"walker"**: un generador de datos sintéticos que simula jugadores moviéndose por Valencia. Publica movimientos (lat, lon, speed, timestamp) al topic `player-movements` con `source="synthetic_walker"` siguiendo el contrato del equipo.

Se usa para dos cosas:

1. **Dev local**: llenar el sistema de eventos sin que nadie tenga que abrir la app y andar.
2. **Demos E2E**: en clase, lanzar el walker + 3 bots de IA para que la partida avance sola mientras enseñamos la página `/analytics` del frontend.

En producción corre como **Cloud Run Job** (no Service — no expone HTTP, solo se dispara y termina).

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **Python 3.12** | Lenguaje común del equipo. Las librerías de geografía (`osmnx`, `shapely`, `networkx`) son de primera clase en Python. |
| **osmnx + networkx** | Para que los jugadores "anden" por calles reales de OpenStreetMap en vez de teletransportarse entre puntos aleatorios. Da realismo a los pasos. |
| **google-cloud-pubsub** | Publica los movements al mismo topic que usaría la app real del frontend. Así Dataflow no distingue entre sintético y humano. |
| **apache-beam[gcp]** | Usado por el `recolector_metricas_local.py` para agregar métricas en modo local (escribe JSONL inspeccionable en `/metrics/` cuando no hay BigQuery disponible). |
| **requests** | Para los bots de IA que atacan el backend HTTP directamente en vez de publicar a Pub/Sub. |

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `juego_caminante.py` | 4 "andadores" sintéticos recorren las 87 zonas de Valencia; cada paso publica a `player-movements`. |
| `bot_ia_riesgo.py` | Bots con heurística tipo Risk (expansión / ataque / defensa / random). Pegan al backend por HTTP, no Pub/Sub. |
| `simulacion_rapida_juego.py` | Simulador acelerado para demos: una partida entera comprimida en ~60 s. |
| `simulacion_multijugador.py` | Ejecuta varias simulaciones en paralelo (test de carga). |
| `recolector_metricas_local.py` | Suscriptor Pub/Sub + pipeline Beam que escribe `.jsonl` en `/metrics` cuando no hay BigQuery. |
| `tabla_reglas_inicio.py` | Siembra en Firestore la tabla de reglas iniciales del juego (zonas, multiplicadores base). Se corre 1 vez al bootstrap. |
| `Dockerfile` | Imagen base del walker, usuario no-root, CMD por defecto `recolector_metricas_local.py`. |
| `requirements.txt` | Pub/Sub, Firestore, Beam, osmnx, networkx, shapely, requests. |

## 🔗 Cómo se conecta con el resto del proyecto

```
data_generator/juego_caminante.py  ──(publish)──▶  Pub/Sub: player-movements
                                                        │
                          ┌─────────────────────────────┼────────────────────────┐
                          ▼                             ▼                        ▼
                     consumer/                     Dataflow                 recolector_metricas_local.py
                     (stdout log)              (→ BigQuery)                 (→ JSONL local)

data_generator/bot_ia_riesgo.py  ──(HTTP)──▶  backend/  (POST /auth, /zones/conquer, /armies/deploy)
```

- **Publisher** del topic `player-movements` (Terraform lo crea en `02_pubsub.tf`).
- **Cliente HTTP** del `backend/` cuando corre como bot de IA.
- Comparte contrato de mensaje con el frontend: `{player_id, timestamp, latitude, longitude, speed_mps}`.

## 🚀 Cómo ejecutarlo

```bash
# Walker local apuntando a emulador Pub/Sub (docker compose up debe estar corriendo)
cd data_generator
pip install -r requirements.txt
PUBSUB_EMULATOR_HOST=localhost:8085 python juego_caminante.py --moves 200 --pause 0.08

# Walker contra Pub/Sub real en GCP
gcloud auth application-default login
PROJECT_ID=cloudrisk-492619 python juego_caminante.py

# Bots de IA atacando el backend local
python bot_ia_riesgo.py --api http://localhost:8080

# Bots contra backend desplegado en Cloud Run
python bot_ia_riesgo.py --api https://cloudrisk-backend-xxxxx.run.app

# Deploy del Cloud Run Job — build + update manual
gcloud builds submit data_generator/ \
  --tag europe-west1-docker.pkg.dev/$PROJECT_ID/cloudrisk/walker:latest
gcloud run jobs update cloudrisk-walker \
  --image europe-west1-docker.pkg.dev/$PROJECT_ID/cloudrisk/walker:latest \
  --region europe-west1

# Disparar el Job ya desplegado
gcloud run jobs execute cloudrisk-walker --region europe-west1
```
