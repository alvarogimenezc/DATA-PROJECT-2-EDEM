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
