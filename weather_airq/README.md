# 🌍 CloudRISK - Ingestores Ambientales (Clima y Calidad del Aire)

Este componente se encarga de extraer datos ambientales en tiempo real (o generarlos de forma sintética) para influir dinámicamente en las mecánicas de juego de **CloudRISK**. Los eventos son enviados a Google Cloud Pub/Sub para que el pipeline unificado los procese.

## 🚀 Funciones Principales

* **Ingestor de Clima (`clima.py`):** Consulta la temperatura, humedad y velocidad del viento en Valencia para calcular un `multiplier` de combate (ej. lluvia o viento fuerte penalizan el ataque).
* **Ingestor de Calidad del Aire (`calidad_aire.py`):** Consulta el índice AQI, PM2.5 y PM10. Una alta contaminación aplica penalizaciones de daño a las tropas.
* **Modo Mock (Fallback Automático):** Si no se detecta una API Key válida, los scripts generan datos aleatorios realistas para poder seguir probando el juego en local sin depender de servicios externos.

## 🛠️ Tecnologías

* **Lenguaje:** Python 3.12.
* **Librerías Clave:** `requests` (Llamadas API REST) y `google-cloud-pubsub` (Mensajería).
* **Construcción:** Multi-stage Docker build para generar contenedores independientes y ligeros.

## ⚙️ Variables de Entorno

Ambos scripts se configuran mediante las siguientes variables:

| Variable | Descripción |
| :--- | :--- |
| `OPENWEATHER_API_KEY` | Tu API Key de OpenWeatherMap. Si se omite, se activa el modo de simulación automática. |
| `PUBSUB_PROJECT` | ID de tu proyecto en Google Cloud (ej. `cloudrisk-492619`). |
| `PUBSUB_TOPIC_WEATHER` | Topic destino para datos climáticos (por defecto: `weather`). |
| `PUBSUB_TOPIC_AIR` | Topic destino para calidad del aire (por defecto: `air-quality`). |
| `INGEST_INTERVAL_SECONDS` | Segundos de pausa entre cada medición (por defecto: `60`). |

## 📦 Cómo Ejecutarlo

El proyecto incluye un `dockerfile` multi-etapa que permite construir de forma independiente el recolector que necesites.

**1. Para construir el ingestor del Clima:**
```bash
docker build -t cloudrisk-weather-ingestor --target weather .
docker run -e PUBSUB_PROJECT=tu-project-id cloudrisk-weather-ingestor