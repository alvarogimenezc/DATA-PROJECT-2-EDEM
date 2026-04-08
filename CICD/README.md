# CI/CD — Cloud Build

Plantillas de Cloud Build para desplegar los servicios CloudRISK a Cloud Run.
Mismo estilo que el repo del profesor (`Serverless_EDEM_2026/GCP/02_Code/03_CICD/`).

## Archivos

- `desplegar_backend_auto.yml` — build de la imagen del backend + deploy a Cloud Run (servicio HTTP).
- `desplegar_walker_auto.yml` — build de la imagen del walker + deploy como Cloud Run Job.

## Lanzar manualmente

```bash
# Backend
gcloud builds submit . --config=CICD/desplegar_backend_auto.yml --project=cloudrisk-492619

# Walker
gcloud builds submit . --config=CICD/desplegar_walker_auto.yml --project=cloudrisk-492619
```

## Conectar a un trigger automático en push a GitHub

```bash
# Crear el repo de Artifact Registry (idempotente, una vez)
gcloud artifacts repositories create cloudrisk-images \
  --project=cloudrisk-492619 \
  --location=europe-west1 \
  --repository-format=docker

# Trigger del backend (cuando cambien archivos en backend/)
gcloud builds triggers create github \
  --project=cloudrisk-492619 \
  --name=cloudrisk-backend-deploy \
  --repo-name=DATA-PROJECT-2-EDEM \
  --repo-owner=TU_USUARIO_GITHUB \
  --branch-pattern=^main$ \
  --build-config=CICD/desplegar_backend_auto.yml \
  --included-files=backend/**

# Trigger del walker
gcloud builds triggers create github \
  --project=cloudrisk-492619 \
  --name=cloudrisk-walker-deploy \
  --repo-name=DATA-PROJECT-2-EDEM \
  --repo-owner=TU_USUARIO_GITHUB \
  --branch-pattern=^main$ \
  --build-config=CICD/desplegar_walker_auto.yml \
  --included-files=data_generator/**
```

> Antes del primer trigger hay que **conectar el repo de GitHub a Cloud Build** desde la consola web (una sola vez): Cloud Build → Triggers → Connect Repository → GitHub.

## Por qué Cloud Build y no GitHub Actions

Mismo enfoque que el repo del profe: el CI/CD vive **dentro de GCP**, no en GitHub. Ventajas:
- No hace falta configurar Workload Identity Federation.
- Los logs de build aparecen en Cloud Build (mismo sitio que el resto de logs del proyecto).
- Las substituciones (`_REGION_ID`, `_BACKEND_IMAGE_NAME`, etc.) son nativas de Cloud Build.
