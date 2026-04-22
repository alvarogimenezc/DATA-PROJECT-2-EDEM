# 🛠️ CloudRISK - Scripts de Operación y Automatización

Este directorio contiene la colección de utilidades, *wrappers* y *seeders* diseñados para simplificar el ciclo de vida del desarrollo, la carga de datos inicial y la ejecución de demostraciones de **CloudRISK**.

## 🚀 Funciones Principales

### 1. Inicialización de Entornos (Bootstrapping)
Scripts para levantar el entorno local completo (Backend + Emuladores + Datos) con un solo comando, disponibles para múltiples sistemas operativos.
* **`bootstrap_demo.sh`** / **`bootstrap_demo.ps1`**: Levantan el backend de FastAPI usando los emuladores de GCP (Firestore y Pub/Sub), inyectan los datos semilla y dejan el sistema listo para recibir peticiones.
* **`setup_local_pubsub.py`**: Configura dinámicamente los *topics* y *subscriptions* requeridos en el emulador local de Pub/Sub.

### 2. Sembrado de Datos (Data Seeding)
Scripts en Python para poblar bases de datos vacías (locales o en la nube) con el estado inicial del juego.
* **`sembrar_firestore.py`**: Inyecta los jugadores base, el mapa de zonas de Valencia y la topología básica en Firestore.
* **`sembrar_demo.py`**: Un script más avanzado que carga un "estado precocinado" (Turno 7, batallas resueltas, territorios repartidos). Ideal para demostraciones de mid-game sin tener que jugar desde cero.
* **`seed_emulators.sh`**: Wrapper en Bash para invocar los scripts de Python específicamente contra los emuladores locales (`FIRESTORE_EMULATOR_HOST`).

### 3. Simuladores de Tráfico
* **`play_demo_game.sh`**: Un orquestador que lanza secuencialmente los bots de IA (`juego_caminante.py` o `simulacion_rapida_juego.py`) para generar actividad automatizada y poblar los dashboards en tiempo real.

## 🛠️ Tecnologías

* **Bash / PowerShell:** Para la orquestación agnóstica del sistema operativo.
* **Python 3.12:** Para la interacción compleja con las APIs de Google Cloud y la manipulación de JSON.
* **GCP Emulators:** Soporte nativo para `google-cloud-cli` (Firestore y Pub/Sub emulators).

## ⚙️ Variables de Entorno Clave

La mayoría de los scripts de sembrado requieren configurar el entorno para distinguir entre desarrollo local y producción.

| Variable | Descripción |
| :--- | :--- |
| `PROJECT_ID` | El identificador del proyecto en GCP (ej. `cloudrisk-492619`). Obligatorio para los scripts de sembrado. |
| `FIRESTORE_EMULATOR_HOST` | Si está definida (ej. `localhost:8080`), los scripts de Python dirigirán el tráfico al emulador en lugar de a la nube. |
| `PUBSUB_EMULATOR_HOST` | Igual que el anterior, pero para Pub/Sub. |

## 📦 Cómo Ejecutarlo

**Para arrancar el entorno de desarrollo local completo:**
```bash
# En Linux/macOS
./scripts/bootstrap_demo.sh

# En Windows
.\scripts\bootstrap_demo.ps1