# scripts/

## 🎯 Qué hace este directorio

Es el **cajón de herramientas** del proyecto. Scripts que no son infra (eso es `infrastructure/`) pero que necesitamos para operar el sistema en dev y demos:

- **Sembrar** Firestore con jugadores, zonas, batallas, balances.
- **Jugar automáticamente** una partida contra el API para que la demo tenga "chicha".
- **Sincronizar** el repo local con el repo del equipo en GitHub.

Todos los scripts "de verdad" están en Python (cross-platform); los `.sh` y `.ps1` son wrappers finos para no tener que recordar el `python scripts/foo.py --flag` completo.

## 🛠️ Lenguajes y tecnologías

| Tech | Por qué aquí |
|---|---|
| **Python 3.12** | Lenguaje común del equipo. Las librerías GCP (`google-cloud-firestore`, `google-cloud-pubsub`) son first-class aquí. |
| **Bash (`.sh`)** | Wrapper cómodo en macOS / Linux / WSL / Git Bash. Solo preflight checks + delega al `.py`. |
| **PowerShell (`.ps1`)** | Equivalente al `.sh` para Windows nativo (Noelia y Martha trabajan así). Mismo resultado, misma flag. |
| **google-cloud-firestore / pubsub** | Clientes oficiales. Escriben directo a Firestore y publican a los topics. |

**Por qué Python y no todo bash:** el seed tiene que correr en Windows, Mac, Linux y dentro de un Cloud Run Job. Bash no corre en PowerShell sin WSL, y PowerShell no corre en un container Linux. Python sí. Los wrappers `.sh`/`.ps1` existen para que cada teammate invoque el script como está acostumbrado.

## 📂 Archivos principales

| Archivo | Qué hace |
|---|---|
| `sembrar_demo.py` | Script principal. Siembra Firestore (4 jugadores, 87 zonas, 38 conquistadas, 3 batallas) + publica 4 mensajes de ejemplo en topics ambientales. Idempotente (`merge=True`). |
| `bootstrap_demo.sh` | Wrapper bash: verifica Python + gcloud, detecta `$PROJECT_ID`, llama al `.py`. |
| `bootstrap_demo.ps1` | Equivalente PowerShell para Windows nativo. |
| `sembrar_firestore.py` | Variante más mínima: solo `players` + `zones` (sin balances ni batallas). Usado por tests. |
| `seed_emulators.sh` | Llama a `sembrar_demo.py` apuntando a los emuladores locales (`localhost:8200`, `localhost:8085`). |
| `play_demo_game.sh` | Contra un backend ya corriendo: logea 4 jugadores, registra 2 más, sincroniza pasos, crea clanes "Pink Lions" y "Cyan Wolves", conquista zonas. Para demos en vivo. |
| `sync_to_team_repo.sh` | Replica cambios de este fork al repo oficial del equipo (`alvarogimenezc/DATA-PROJECT-2-EDEM`). |

## 🔗 Cómo se conecta con el resto del proyecto

```
scripts/sembrar_demo.py
          │
          ├─▶ Firestore   (users, zones, user_balance, location_balance, battles)
          └─▶ Pub/Sub     (weather-events, airquality-events — 4 mensajes de ejemplo)

scripts/play_demo_game.sh ──▶ backend/ (HTTP: /auth, /clans, /armies, /zones)

infrastructure/terraform/10_demo_seed.tf ──▶ scripts/sembrar_demo.py (automático tras apply)

Lee de:
  data/demo_game_state.json         (estado precocinado)
  data/players.json                 (usuarios demo)
  backend/cloudrisk_api/...          (constante VALENCIA_ZONES)
```

**Orden típico tras un `terraform apply`:**

1. `bash scripts/bootstrap_demo.sh cloudrisk-492619` (o `.ps1` en Windows)
2. `bash scripts/play_demo_game.sh` (solo si quieres estado "a mitad de partida" con clanes)
3. `python scripts/sembrar_demo.py --project cloudrisk-492619 --dry-run` para confirmar que todo entró (compara contra Firestore sin escribir)

## 🚀 Cómo ejecutarlo

```bash
# Seed completo contra Firestore real (requiere gcloud auth application-default login)
python scripts/sembrar_demo.py --project cloudrisk-492619

# Mismo, pero con wrapper (detecta Python, valida gcloud, instala deps mínimas)
bash scripts/bootstrap_demo.sh cloudrisk-492619

# Windows nativo (PowerShell)
powershell -File scripts/bootstrap_demo.ps1 -Project cloudrisk-492619

# Contra emulador local (docker compose up debe estar corriendo)
FIRESTORE_EMULATOR_HOST=localhost:8200 \
PUBSUB_EMULATOR_HOST=localhost:8085 \
python scripts/sembrar_demo.py --project cloudrisk-local

# Seed mínimo (solo users + zones) — útil para tests
python scripts/sembrar_firestore.py --project cloudrisk-492619

# Simular partida en vivo contra un backend ya desplegado
API=http://localhost:8080 bash scripts/play_demo_game.sh

# Dry-run: qué haría sin tocar Firestore
python scripts/sembrar_demo.py --project cloudrisk-492619 --dry-run
```
