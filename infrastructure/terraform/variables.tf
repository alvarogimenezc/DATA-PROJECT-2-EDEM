# ┌─────────────────────────────────────────────────────────────────────────┐
# │ variables.tf                                                            │
# │                                                                         │
# │ Los "inputs" de Terraform. Nunca pongas valores a mano dentro de los    │
# │ .tf — se ponen aqui como variables y se rellenan desde terraform.tfvars │
# │ (que esta gitignored para no subir secretos a GitHub).                  │
# │                                                                         │
# │ Analogia: variables.tf es el formulario de entrada a una fabrica.       │
# │ Los .tf que usan las variables son las maquinas de la fabrica.          │
# └─────────────────────────────────────────────────────────────────────────┘

# -----------------------------------------------------------------------------
# project_id: identificador global del proyecto GCP donde se crean las cosas
# -----------------------------------------------------------------------------
# Se saca de la consola o con `gcloud projects list`.
# Es un string unico a nivel mundial — no se puede repetir entre cuentas.
variable "project_id" {
  description = "ID del proyecto GCP (ej: cloudrisk-492619)"
  type        = string
}

# -----------------------------------------------------------------------------
# region: donde se desplegan fisicamente los recursos
# -----------------------------------------------------------------------------
# Elegimos europe-west1 (Belgica) porque:
#   - es la mas cercana a Valencia con todos los servicios que usamos
#   - tiene precios mas bajos que europe-west3 (Frankfurt)
#   - Firestore Native tiene una region multi-regional "eur3" encima
variable "region" {
  description = "Region GCP donde crear los recursos"
  type        = string
  default     = "europe-west1"
}

# -----------------------------------------------------------------------------
# jwt_secret: clave para firmar los tokens JWT del backend
# -----------------------------------------------------------------------------
# sensitive = true => Terraform NO imprime el valor en la terminal.
# Lo metemos en Secret Manager (no en el codigo de la API). La API lo lee
# en runtime desde ahi. Si el jwt_secret cambia, TODOS los tokens existentes
# se invalidan automaticamente.
variable "jwt_secret" {
  description = "Clave secreta para firmar tokens JWT del backend (minimo 32 chars aleatorios)"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# scheduler_secret: token compartido entre Cloud Scheduler y el backend para
# endpoints internos (/turn/setup, /battles/resolve-expired, /multipliers/reset).
# Lo manda Scheduler en el header X-Scheduler-Token; el backend compara con este
# valor cargado desde Secret Manager. En modo USE_LOCAL_STORE=1 el backend salta
# la validación para que los tests y el dev local no necesiten el token.
# -----------------------------------------------------------------------------
variable "scheduler_secret" {
  description = "Token compartido con Cloud Scheduler para endpoints internos"
  type        = string
  sensitive   = true
}

# ─── Parámetros del pipeline unificado (stateful DoFn) ──────────────────────
# Consumidos por el job Dataflow. Cámbialos sin re-deploy del pipeline: el
# runtime lee estos valores del parameters{} del flex template job.

variable "power_per_steps" {
  description = "Número de pasos que equivalen a 1 army en el scoring"
  type        = number
  default     = 500
}

variable "daily_army_cap" {
  description = "Máximo de armies ganables por pasos en un día (por usuario)"
  type        = number
  default     = 50
}

variable "max_speed_kmh" {
  description = "Velocidad máxima aceptada; eventos por encima van a DLQ (anti-trampa)"
  type        = number
  default     = 15
}

variable "daily_steps_cap" {
  description = "Máximo de pasos/día aceptados por usuario (anti-trampa). El exceso se descarta."
  type        = number
  default     = 30000
}
