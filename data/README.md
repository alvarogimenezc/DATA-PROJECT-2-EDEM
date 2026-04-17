# data/

## 🎯 Qué hace este directorio

Carpeta de **datos estáticos en JSON**. No hay código ejecutable aquí — solo ficheros que otros scripts leen para arrancar la demo, pasar tests offline o mapear usuarios externos a jugadores de CloudRISK.

Piensa en esto como las "semillas" del proyecto: si borras Firestore y corres `scripts/sembrar_demo.py`, los datos que entran vienen de aquí.

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **JSON** | Es el formato universal: Python lo lee con `json.load`, JavaScript con `JSON.parse`, Firestore ingiere dict de Python directo. Ningún parser custom, ninguna dependencia. |
| (nada más) | No hay código. El objetivo es justamente que no haya lógica — solo datos versionados en Git para que cualquier miembro del equipo pueda editarlos en un PR. |

**Por qué JSON y no YAML/CSV:** los seeds tienen estructuras anidadas (jugadores → zonas → clanes con arrays de coordenadas). YAML es más legible pero genera errores por indentación; CSV no aguanta anidados. JSON es el punto medio: estricto, anidable y lo entiende cualquier herramienta.

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `demo_game_state.json` | Estado "precocinado" de una partida a la mitad: 4 comandantes, 38 zonas conquistadas, 3 batallas en el histórico. Lo aplica `sembrar_demo.py` con `merge=True` (idempotente). |
| `players.json` | 4 jugadores demo (norte/sur/este/oeste @ cloudrisk.app, pass `demo1234`). Lo usan `sembrar_firestore.py` y el store local del backend cuando `USE_LOCAL_STORE=1`. |
| `mock_tracker_feed.json` | Feed falso de `random_tracker` con un paseo real por Valencia (Cabañal → Malvarrosa). Lo consume el fetcher en `steps_ingestor/` con `--local-file` para tests sin red. |
| `random_tracker_mapping.json` | Mapea `username` del tracker externo → `player_id` de CloudRISK. La clave `"*"` es el fallback si un movement llega sin `user`. |

## 🔗 Cómo se conecta con el resto del proyecto

```
data/demo_game_state.json  ──▶  scripts/sembrar_demo.py  ──▶  Firestore (users, zones, battles, balances)
data/players.json          ──▶  scripts/sembrar_firestore.py  ──▶  Firestore (users)
                           └──▶  backend local_store (USE_LOCAL_STORE=1)
data/mock_tracker_feed.json ─▶  steps_ingestor/recolector_pasos_diario.py  --local-file   (tests offline)
data/random_tracker_mapping.json ─▶  steps_ingestor/*.py  (resolver user → player_id)
```

- **No se despliega a ningún servicio**: solo se lee desde scripts que corren en tu máquina o en un Cloud Run Job.
- Si cambias algo aquí, re-ejecuta `bash CICD/sembrar_demo.sh` para propagarlo a Firestore.

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
bash CICD/sembrar_demo.sh cloudrisk-492619

# Verificar que el seed quedó bien
bash CICD/verificar_demo.sh cloudrisk-492619
```

**Reglas de oro del equipo:**

- Si editas un JSON aquí, corre `python -m json.tool <fichero>` antes del commit. Un `,` colgado rompe el seed entero y Noelia te va a sacar los ojos.
- Los campos `_comment` dentro de los JSON son documentación — **no los borres**. Los parsers los ignoran.
- Si añades un jugador nuevo, hazlo en `players.json` **y** en `demo_game_state.json` con el mismo `id` para que todo case.
