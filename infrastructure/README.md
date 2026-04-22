# 🏗️ CloudRISK - Infraestructura (GCP + Terraform)

Este directorio contiene la definición completa de la infraestructura en la nube para **CloudRISK**. Basado en el principio de **Infraestructura como Código (IaC)**, permite desplegar, escalar y destruir todo el ecosistema del proyecto (Backend, Frontend, Base de Datos y Pipelines) de forma reproducible en Google Cloud Platform (GCP).

## 📂 Contenido del Directorio

* **`terraform/`**: Contiene los archivos de configuración `.tf` que definen los recursos de GCP (Cloud Run, Firestore, Pub/Sub, IAM, etc.).
* **`deploy.sh`**: Script de automatización para simplificar el proceso de despliegue inicial y gestión de credenciales.

## 🚀 Despliegue Automatizado (`deploy.sh`)

El script `deploy.sh` es la herramienta recomendada para el despliegue inicial, ya que gestiona pasos críticos de configuración que Terraform no puede hacer por sí solo:

1. **Autenticación:** Verifica que el usuario tenga sesiones activas en `gcloud` y Application Default Credentials (ADC).
2. **Configuración de Docker:** Configura el acceso de Docker al Artifact Registry de Google para permitir la subida de imágenes.
3. **Habilitación de APIs:** Activa los servicios necesarios en el proyecto de GCP (Cloud Run, Dataflow, Secret Manager, etc.) antes de lanzar Terraform.
4. **Ciclo Terraform:** Ejecuta automáticamente los comandos `init`, `plan` y `apply`.

**Uso:**
```bash
# Otorgar permisos de ejecución
chmod +x deploy.sh

# Ejecutar el despliegue
./deploy.sh