# 📚 CloudRISK - Documentación Técnica y Troubleshooting

Este directorio actúa como la base de conocimiento operativo del proyecto. Contiene informes post-mortem y guías de resolución de problemas (troubleshooting) documentadas durante el ciclo de vida de la infraestructura de **CloudRISK**.

## 📄 Archivos de Referencia

### 1. Guía de 50 Errores Comunes (`gcp_terraform_50_common_errors.md`)
* **¿Qué es?** Un manual de supervivencia para el trabajo con Infraestructura como Código (IaC).
* **¿Qué contiene?** Una lista curada de los 50 fallos más habituales al operar con Terraform y Google Cloud Platform. Está dividida en:
  * **Parte 1:** Errores de CLI, bloqueos de estado (`state lock`), dependencias cíclicas y fallos de providers.
  * **Parte 2:** Errores específicos de servicios GCP como Cloud Run, Dataflow, Pub/Sub, Artifact Registry y conflictos de IAM.
* **Estructura:** Cada entrada presenta el *Síntoma* (mensaje de la consola), la *Causa* raíz y el *Fix* (comando o código para solucionarlo).

### 2. Informe de Despliegue (`terraform_deploy_errors.md`)
* **¿Qué es?** Un documento de auditoría y post-mortem sobre la estabilización del despliegue en el entorno de producción.
* **¿Qué contiene?** El registro paso a paso de las iteraciones necesarias para lograr un ciclo `apply ⇄ destroy` completamente limpio.
* **Hallazgos Clave Documentados:** * Resolución de errores 409 (conflictos de estado en Firestore).
  * Corrección de dependencias de compilación Docker (`depends_on` ausentes en Cloud Run Jobs).
  * Solución a los bloqueos de permisos de lectura en Artifact Registry para los workers de Dataflow.
  * Auditoría y limpieza de recursos huérfanos (topics de Pub/Sub y buckets no gestionados).

## 🚀 Cómo utilizar esta carpeta

* **Si un `terraform apply` falla:** Antes de buscar en internet, revisa el archivo `gcp_terraform_50_common_errors.md`. Es altamente probable que el mensaje de error (ej. *Access to secret denied* o *Image not found*) ya esté documentado con su solución exacta.
* **Para entender la arquitectura de CI/CD:** El archivo `terraform_deploy_errors.md` explica decisiones de diseño sobre el orden de despliegue (ej. por qué ciertos recursos necesitan un `depends_on` explícito hacia las imágenes de Docker).
