# 10_demo_seed.tf — Semilla AUTOMÁTICA de datos demo tras `terraform apply`.
#
# Qué hace
# --------
# Un `null_resource` con `local-exec` que, cuando terminan de crearse los
# topics de Pub/Sub y el database de Firestore, corre:
#     python scripts/sembrar_demo.py --project <PROJECT>
#
# Resultado: tras `terraform apply`, Firestore ya tiene:
#   - 4 jugadores demo (login norte/sur/este/oeste @ cloudrisk.app, pass=demo1234)
#   - 87 zonas de Valencia (38 ya conquistadas por los 4 clanes)
#   - user_balance + location_balance (contrato del equipo)
#   - Histórico de 3 batallas
# Y 4 mensajes de ejemplo publicados en los topics ambientales.
#
# Si quieres DESACTIVARLO (p.ej. en CI sin Python local), setea la variable
# `seed_demo_on_apply = false` en tu `terraform.tfvars`.
#
# Cross-platform
# --------------
# Terraform elige automáticamente el interpreter según el OS del que corre
# `terraform apply`:
#   - Windows:   uses `powershell.exe`
#   - macOS/Linux: uses `sh`
# Y en ambos casos delega en el mismo sembrar_demo.py (Python puro).
#
# Idempotencia
# ------------
# El script usa merge=True en Firestore, así que re-ejecutarlo NO crea
# duplicados. El trigger `always = timestamp()` fuerza re-ejecución en cada
# apply; si prefieres que sólo corra una vez, cambia a un trigger fijo.

variable "seed_demo_on_apply" {
  description = "Si true, corre scripts/sembrar_demo.py tras terraform apply."
  type        = bool
  default     = true
}

resource "null_resource" "seed_demo" {
  count = var.seed_demo_on_apply ? 1 : 0

  depends_on = [
    google_project_service.apis["firestore.googleapis.com"],
    google_pubsub_topic.air_quality,
    google_pubsub_topic.weather,
    google_pubsub_topic.player_movements,
  ]

  # Re-corre en cada apply. Si prefieres una única ejecución, cambia a:
  #   triggers = { static = "once" }
  triggers = {
    always_run = timestamp()
  }

  # Windows: usa PowerShell
  provisioner "local-exec" {
    when        = create
    on_failure  = continue
    interpreter = ["powershell.exe", "-NoProfile", "-Command"]
    command     = "python '${path.root}/../../scripts/sembrar_demo.py' --project '${var.project_id}'"
    # En hosts no-Windows Terraform ignora este bloque si el interpreter falta;
    # fallback: el siguiente provisioner (sh) toma el relevo.
  }
}

# Alternativa si el host es Unix y PowerShell falla (Terraform lo intenta
# siempre, pero si no hay pwsh.exe este bloque asume el control):
resource "null_resource" "seed_demo_unix" {
  count = var.seed_demo_on_apply ? 1 : 0

  depends_on = [null_resource.seed_demo]

  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    when        = create
    on_failure  = continue
    interpreter = ["/bin/sh", "-c"]
    command     = "command -v python3 >/dev/null && python3 ${path.root}/../../scripts/sembrar_demo.py --project ${var.project_id} || echo 'skipping: python3 no disponible o ya se sembró vía PowerShell'"
  }
}

output "demo_seed_command" {
  description = "Comando para sembrar demo manualmente si el auto-seed falló."
  value       = "python scripts/sembrar_demo.py --project ${var.project_id}"
}

output "demo_login_example" {
  description = "Credencial de demo lista para usar."
  value       = "norte@cloudrisk.app / demo1234 (ver data/demo_game_state.json para los otros 3)"
}
