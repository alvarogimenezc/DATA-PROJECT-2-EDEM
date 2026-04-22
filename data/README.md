# 📂 data/ — Semillas y Archivos de Guardado (Data Seeding)

Este directorio contiene **datos estáticos en formato JSON**. No es código ejecutable, sino los archivos de configuración y estados base que consumen otros componentes del sistema.

Funciona como una colección de **"Partidas Guardadas"** y datos de prueba. Permite inicializar el entorno de CloudRISK con jugadores, territorios y estadísticas preconfiguradas, facilitando pruebas de integración sin necesidad de generar datos desde cero tras cada reseteo de base de datos.

---

## 📄 Estructura de Archivos

### 1. `players.json` (Perfiles Iniciales)
* **¿Qué es?** Los perfiles base de los 4 comandantes de demostración.
* **¿Qué contiene?** Credenciales de acceso (por defecto `demo1234`), colores de clan (HEX), zonas de inicio (ej. `zona-borbot`) y recursos base (10 ejércitos y 500 de oro).
* **Uso:** Leído por el backend en modo local y por los scripts de sembrado para inyectarlos en Google Firestore.

### 2. `demo_game_state.json` (Estado de Partida Avanzado)
* **¿Qué es?** Un estado de juego "precocinado" para demostraciones o validación de lógicas de mid-game.
* **¿Qué contiene?** Una partida simulada en el **Turno 7**. Incluye 38 zonas conquistadas distribuidas entre los 4 jugadores, un historial con 3 batallas resueltas y métricas sintéticas ambientales (clima y calidad del aire).
* **Uso:** Procesado por `sembrar_demo.py` para construir un escenario completo en Firestore y BigQuery.

### 3. `mock_tracker_feed.json` (Simulación de Movimiento)
* **¿Qué es?** Archivo para probar el pipeline de recolección de pasos en entornos sin acceso a APIs de tracking reales.
* **¿Qué contiene?** Telemetría GPS sintética que simula una ruta de 4.8 km y ~4350 pasos a lo largo de 10 puntos de control.
* **Uso:** Ingerido por el recolector de pasos cuando se ejecuta con el flag `--local-file`.

### 4. `random_tracker_mapping.json` (Mapeo de Identidades)
* **¿Qué es?** Un diccionario de resolución de identidades.
* **¿Qué contiene?** Asocia los *usernames* recibidos desde los dispositivos de tracking con los IDs internos de los jugadores en Firestore (ej: `demo-player-001`). Incluye un comodín `"*"` como fallback para eventos no asignados.
* **Uso:** Utilizado por los scripts de ingestión para asegurar la correcta atribución de recursos.

---

## 🚀 Cómo Inyectar los Datos

Estos archivos no se ejecutan por sí solos. Para poblar los servicios en la nube o en local, se utilizan los scripts de la raíz del proyecto. 

Desde la consola, ejecuta los siguientes comandos:

**1. Sembrar el estado completo (Partida Avanzada) en Firestore:**
```bash
python scripts/sembrar_demo.py --project <TU_PROJECT_ID>