# 📂 data/ — Semillas y Archivos de Guardado (Data Seeding)

Aquí tenemos **datos estáticos en formato JSON**. No es código ejecutable, solo archivos que necesitan los demás programas para funcionar.

Funciona como una colección de **"Partidas Guardadas"**. Permite arrancar el juego directamente con jugadores, territorios y estadísticas reales en Google Cloud, sin tener que empezar desde cero cada vez que se borra la base de datos para hacer pruebas.

---

##  Explicación de los 4 Archivos

### 1. `players.json` (Las cuentas de prueba)
* [cite_start]**¿Qué es?** Los perfiles base de nuestros 4 comandantes de demostración (Norte, Sur, Este y Oeste)[cite: 17, 29, 39, 50].
* [cite_start]**¿Qué contiene?** Sus credenciales de acceso (la contraseña es `demo1234`), los colores de su clan en formato hexadecimal, su barrio inicial en el mapa y sus recursos de partida nueva (como 10 ejércitos y 500 de oro iniciales)[cite: 19, 20, 21, 22, 24].
* **¿Quién lo usa?** El backend al arrancar (para guardar en memoria local) y los scripts de sembrado para inyectarlos en Google Firestore.

### 2. `demo_game_state.json` (La partida a la mitad)
* [cite_start]**¿Qué es?** Un estado de juego "precocinado" para que las presentaciones y demos de CloudRISK luzcan espectaculares desde el segundo uno[cite: 78].
* [cite_start]**¿Qué contiene?** Una partida avanzada en el **Turno 7**[cite: 85], donde los comandantes ya tienen niveles altos. [cite_start]Incluye **38 zonas ya conquistadas** repartidas por Valencia [cite: 154][cite_start], un historial interactivo con 3 batallas recientes [cite: 220, 225, 234, 243] [cite_start]y un registro histórico de clima y calidad del aire para que las gráficas de BigQuery no salgan vacías[cite: 254, 255].
* **¿Quién lo usa?** El script `sembrar_demo.py` para construir todo este mapa instantáneo en Firestore.

### 3. `mock_tracker_feed.json` (El paseo simulado)
* [cite_start]**¿Qué es?** Un archivo para probar el sistema de recolección de pasos del juego sin tener que salir a la calle a caminar realmente para hacer pruebas[cite: 58].
* [cite_start]**¿Qué contiene?** Los datos GPS falsos de una ruta matutina por Valencia (del Cabañal a la Malvarrosa), simulando una caminata de unos 4.8 km a lo largo de 10 puntos de control[cite: 58, 61, 65, 74].
* **¿Quién lo usa?** El recolector local (`recolector_pasos_diario.py`) cuando lo ejecutamos en modo de pruebas local (`--local-file`).

### 4. `random_tracker_mapping.json` (El traductor de usuarios)
* [cite_start]**¿Qué es?** Una pequeña agenda o diccionario que conecta nuestra app que cuenta los pasos con la base de datos del juego[cite: 2].
* [cite_start]**¿Qué contiene?** Asocia los nombres de usuario reales de la pulsera o tracker (ej: "francisco", "noelia") con los identificadores internos del juego (ej: `demo-player-001`, `demo-player-003`)[cite: 5, 8]. [cite_start]También incluye un comodín `"*"` por si nos llega un paso sin nombre asignado[cite: 4].
* **¿Quién lo usa?** Los scripts de ingestión de pasos, para saber a qué jugador deben sumarle los puntos.

---

## ⚙️ Cómo inyectar estos datos a Google Cloud

Esta carpeta no se ejecuta por sí sola. Para mandar estos datos a la nube, hay usar los scripts de la carpeta principal. Abre la terminal y ejecuta:

```bash
# Para mandar la partida completa a Firestore
python scripts/sembrar_demo.py --project cloudrisk-492619

# Para mandar solo los usuarios iniciales a Firestore
python scripts/sembrar_firestore.py --project cloudrisk-492619

## Cómo se conecta con el resto del proyecto

```
data/demo_game_state.json  ──▶  scripts/sembrar_demo.py  ──▶  Firestore (users, zones, battles, balances)
data/players.json          ──▶  scripts/sembrar_firestore.py  ──▶  Firestore (users)
                           └──▶  backend local_store (USE_LOCAL_STORE=1)
data/mock_tracker_feed.json ─▶  steps_ingestor/recolector_pasos_diario.py  --local-file   (tests offline)
data/random_tracker_mapping.json ─▶  steps_ingestor/*.py  (resolver user → player_id)
```

- **No se despliega a ningún servicio**: solo se lee desde scripts que corren en tu máquina o en un Cloud Run Job.
- Si cambias algo aquí, re-ejecuta `python scripts/sembrar_demo.py --project <ID>` para propagarlo a Firestore.

## 🚀 Cómo ejecutarlo

Este directorio no se "ejecuta". Lo que hacen los demás con él:

```bash
# Sembrar Firestore con demo_game_state.json + players.json
python scripts/sembrar_demo.py --project cloudrisk-492619

# Correr el fetcher de pasos en modo offline (usa mock_tracker_feed.json)
python steps_ingestor/recolector_pasos_diario.py --local-file data/mock_tracker_feed.json

# Validar que un JSON es sintácticamente correcto antes de commitear
python -m json.tool data/demo_game_state.json > /dev/null && echo OK

# Tras editar: re-sembrar para que los cambios entren en Firestore
python scripts/sembrar_demo.py --project cloudrisk-492619

# Verificar que el seed quedó bien (dry-run que compara)
python scripts/sembrar_demo.py --project cloudrisk-492619 --dry-run
```



- Los campos `_comment` dentro de los JSON son documentación — **no los borres**. Los parsers los ignoran.
- Si se añade un jugador nuevo, se debe hacer en `players.json` **y** en `demo_game_state.json` con el mismo `id` para que todo case.
