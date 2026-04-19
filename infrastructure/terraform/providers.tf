# ┌─────────────────────────────────────────────────────────────────────────┐
# │ providers.tf                                                            │
# │                                                                         │
# │ Aqui le decimos a Terraform:                                            │
# │   1) Que version de Terraform queremos (>= 1.8)                         │
# │   2) Que "proveedor de nube" vamos a usar (Google Cloud)                │
# │   3) Donde se guarda el STATE (gs://... en Google Cloud Storage)        │
# │                                                                         │
# │ El STATE es un JSON que lleva la contabilidad de TODO lo que Terraform  │
# │ ha creado en GCP. Si lo pierdes, Terraform piensa que no ha creado      │
# │ nada y te duplica recursos. Por eso lo guardamos en un bucket GCS.      │
# │                                                                         │
# │ Analogia: providers.tf es la "caratula del libro" — dice en que idioma  │
# │ esta escrito y donde vive la bibliografia.                              │
# └─────────────────────────────────────────────────────────────────────────┘

terraform {
  required_version = ">= 1.8"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0" # ~> 5.0 significa "cualquier 5.x", no actualiza a 6
    }
    # google-beta es necesario para google_dataflow_flex_template_job (12_dataflow.tf).
    # Usa las mismas credenciales que `google`; es solo una "versión preview" del provider.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # STATE remoto en GCS — IMPORTANTE: este bucket debe existir ANTES de
  # correr `terraform init`. Lo creamos a mano una sola vez con:
  #   gsutil mb -l europe-west1 gs://cloudrisk-492619-tfstate
  backend "gcs" {
    bucket = "cloudrisk-492619-tfstate"
    prefix = "terraform/state"
  }
}

# El provider "google" se conecta con las credenciales de `gcloud auth
# application-default login` si no le pasas nada mas. Simple y util en clase.
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
