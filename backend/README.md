# ⚙️ CloudRISK - Backend (FastAPI)

Este componente es el corazón de **CloudRISK**. Es una API REST que gestiona toda la lógica del juego: autenticación, conquistas territoriales de Valencia, cálculo de turnos y sincronización en tiempo real vía WebSocket.

## 🚀 Funciones Principales
* **Gestión de Usuarios y Clanes:** Autenticación por JWT (Bearer token).
* **Control Territorial (`zonas.py`, `ejercitos.py`):** Lógica de conquista atómica, despliegue de tropas y combate estilo Risk.
* **Integración Física (`pasos.py`):** Convierte los pasos reales (enviados por Pub/Sub) en poder militar.
* **Inteligencia Artificial (`simulador.py`, `bot_meta.py`):** Bots que simulan turnos evaluando prioridades tácticas (defensa, ataque, expansión).
* **WebSocket en Tiempo Real:** Actualizaciones inmediatas al cliente sobre batallas, posiciones y turnos.

## 🛠️ Tecnologías
* **Framework:** FastAPI (Python 3.12) con Uvicorn.
* **Base de Datos:** Google Cloud Firestore (Producción) o Almacén en Memoria RAM (Desarrollo local).
* **Mensajería:** Google Cloud Pub/Sub (`google-cloud-pubsub`).
* **Geometría:** `shapely` (Para calcular adyacencia de los barrios).

## ⚙️ Variables de Entorno Clave
La API lee su configuración de `.env` o variables inyectadas.

| Variable | Descripción |
| :--- | :--- |
| `USE_LOCAL_STORE` | `1` para usar RAM local, `0` para usar Firestore real. |
| `PROJECT_ID` | ID de tu proyecto en Google Cloud. |
| `SECRET_KEY` | Clave secreta para firmar los tokens JWT. |
| `SCHEDULER_SECRET` | Token de seguridad para los endpoints llamados por Cloud Scheduler. |
| `PORT` | Puerto de escucha (por defecto 8080). |

*Nota: Al arrancar, si `USE_LOCAL_STORE=1`, el sistema siembra automáticamente 87 barrios de Valencia y 4 jugadores de demostración para poder jugar sin infraestructura externa.*

## 📦 Cómo Ejecutarlo

**En Local (Modo RAM):**
```bash
# Desde la carpeta backend/
export USE_LOCAL_STORE=1
pip install -r requirements.txt
uvicorn cloudrisk_api.main:app --reload --port 8080