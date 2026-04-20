# Generador de Datos Sintéticos (WalkRisk)

## 🎯 ¿Para qué sirve esta carpeta?

Esta carpeta contiene los simuladores que hemos creado para el proyecto WalkRisk. Dado que no podemos generar miles de pasos físicos reales para evaluar la arquitectura Cloud, hemos creado scripts que simulan la actividad de varios jugadores en Valencia. 

Con estos scripts generamos eventos (latitud, longitud, velocidad y tiempo) y los inyectamos en nuestro sistema de **Pub/Sub** de Google Cloud para probar que nuestras pipelines de Dataflow y BigQuery funcionan correctamente.

## 📂 Archivos del módulo

| Archivo | Qué hace |
|---|---|
| `juego_caminante.py` | Simula a 4 personas caminando por los 87 barrios de Valencia; envía los pasos a Pub/Sub. |
| `bot_ia_riesgo.py` | Inteligencia Artificial para el juego. Simula decisiones de ataque o defensa basadas en los ejércitos disponibles. |
| `simulacion_rapida_juego.py` | Acelerador de partidas. Lo utilizamos para llenar las bases de datos rápidamente y poder mostrar los Dashboards en las demos. |
| `recolector_metricas_local.py` | Script de respaldo para guardar los logs de Pub/Sub en local (archivos `.jsonl`) si falla la nube. |
| `tabla_reglas_inicio.py` | Script que inicializa el mapa de Firestore con los territorios la primera vez que se lanza el juego. |


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
## 🚀 Cómo lo ejecutamos para las pruebas

1. **Lanzar caminantes locales (para ver cómo funciona GCP):**
```bash
gcloud auth application-default login
export PROJECT_ID=cloudrisk-492619
python juego_caminante.py --moves 200