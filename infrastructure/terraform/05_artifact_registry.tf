# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 05_artifact_registry.tf — Registro de imagenes Docker                   │
# │                                                                         │
# │ Artifact Registry es el "Docker Hub privado" de GCP. Cada vez que       │
# │ Cloud Build compila una imagen, la sube aqui. Cloud Run luego tira de   │
# │ aqui para arrancar los contenedores.                                    │
# │                                                                         │
# │ URL de una imagen = REGION-docker.pkg.dev/PROJECT/REPO/IMAGE:TAG        │
# │ Ej: europe-west1-docker.pkg.dev/cloudrisk-492619/cloudrisk/api:latest   │
# │                                                                         │
# │ Analogia: es como GitHub pero para imagenes Docker. Un sitio privado    │
# │ donde guardar lo que construyes.                                        │
# └─────────────────────────────────────────────────────────────────────────┘

resource "google_artifact_registry_repository" "cloudrisk" {
  location      = var.region
  repository_id = "cloudrisk" # Nombre del repo — parte de la URL de cada imagen
  description   = "Imagenes Docker de los servicios CloudRISK"
  format        = "DOCKER"

  # Limpieza automatica: conserva solo las ultimas 5 versiones de cada imagen.
  # Evita pagar por 300 imagenes antiguas que nadie va a usar.
  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  labels = {
    course = "serverless-edem-2026"
  }

  depends_on = [google_project_service.apis]
}
