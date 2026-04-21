# Guía — 50 errores comunes en GCP + Terraform

> Cada entrada sigue el mismo patrón:
> **Síntoma** (mensaje de error típico) → **Causa raíz** → **Fix**.
>
> Las 10 primeras las vivimos en este repo desplegando CloudRISK (ver [`terraform_deploy_errors.md`](./terraform_deploy_errors.md)); el resto son los baches que todo equipo encuentra antes o después trabajando con Terraform + GCP.

---

## Parte 1 — Errores de Terraform (core/CLI, state, providers)

### 1. `terraform: command not found`
**Síntoma:** `bash: terraform: command not found` o `'terraform' is not recognized as an internal or external command`.
**Causa:** binario no instalado o no en `$PATH`.
**Fix:** descargar de https://releases.hashicorp.com/terraform/ el zip adecuado para tu arch/OS y colocar `terraform.exe` en una carpeta del `$PATH`. En Windows, `~/bin/` (Git Bash) o `C:\HashiCorp\` + actualizar System PATH.

### 2. `Error: Missing required argument` al hacer `plan`/`apply`
**Síntoma:** `Error: No value for required variable. variable "jwt_secret"`.
**Causa:** una variable declarada sin `default` en `variables.tf` no se está pasando por `-var`, `-var-file` ni `TF_VAR_*`.
**Fix:** crear `terraform.tfvars` (gitignored) y rellenar los valores, o pasar `-var='jwt_secret=…'` desde la CLI.

### 3. `Error: Backend configuration changed`
**Síntoma:** `A change in the backend configuration has been detected … Run "terraform init" with the "-reconfigure" or "-migrate-state" option`.
**Causa:** cambiaste el bucket del backend GCS o el `prefix` en `providers.tf`.
**Fix:** `terraform init -migrate-state` (mueve el state al nuevo destino) o `-reconfigure` (abandona y reinicializa — *pierde* la referencia al state anterior).

### 4. `Error acquiring the state lock`
**Síntoma:** `Error message: 2 matches when locking the state`.
**Causa:** otro `apply` está en curso o un proceso anterior murió sin liberar el lock.
**Fix:** `terraform force-unlock <LOCK_ID>` (solo si estás 100 % seguro de que no hay otro apply corriendo).

### 5. `Error: Provider configuration not present`
**Síntoma:** `Provider "google-beta" requires explicit configuration` pese a tenerlo en `required_providers`.
**Causa:** falta un bloque `provider "google-beta" { … }` con las credenciales/región.
**Fix:** añadir un bloque `provider "google-beta" { project = var.project_id  region = var.region }`.

### 6. `Error: Error 409: Database already exists` (Firestore, BigQuery dataset, bucket…)
**Síntoma:** `Error creating X: googleapi: Error 409: … already exists`.
**Causa:** el recurso ya está en GCP pero no en tu `tfstate` (despliegue anterior desde otra máquina, o state reseteado).
**Fix:** `terraform import <resource-address> <id>`. Para Firestore: `terraform import google_firestore_database.cloudrisk 'projects/PROJECT/databases/(default)'`.

### 7. Dependencias implícitas rotas — race conditions
**Síntoma:** `Error: Image not found: europe-west1-docker.pkg.dev/.../foo:latest`.
**Causa:** el recurso que usa la imagen no tiene `depends_on` al `null_resource` que la construye. Terraform los crea en paralelo y pierde la carrera.
**Fix:** añadir `depends_on = [null_resource.image_foo]` al recurso consumidor.

### 8. `local-exec` con Docker Desktop apagado
**Síntoma:** `ERROR: error during connect … open //./pipe/dockerDesktopLinuxEngine: El sistema no puede encontrar el archivo especificado`.
**Causa:** Docker Desktop no está corriendo cuando Terraform ejecuta `docker build/push`.
**Fix:** arrancar Docker Desktop y esperar a que `docker info` responda. Opcional: envolver el `local-exec` en un `until docker info >/dev/null 2>&1; do sleep 2; done && …` para ser resiliente.

### 9. `docker push … denied: Permission artifactregistry.repositories.uploadArtifacts denied`
**Síntoma:** `denied: Permission 'artifactregistry.repositories.uploadArtifacts' denied on resource`.
**Causa:** el usuario humano (o la SA) no tiene `roles/artifactregistry.writer`. En local, además falta `gcloud auth configure-docker REGION-docker.pkg.dev`.
**Fix:** `gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet` y `gcloud projects add-iam-policy-binding … --role roles/artifactregistry.writer --member user:EMAIL`.

### 10. Dataflow worker sin `roles/artifactregistry.reader`
**Síntoma:** job en `JOB_STATE_FAILED` justo al arrancar; en Logging: `docker: Error response from daemon: denied: Permission 'artifactregistry.repositories.downloadArtifacts' denied`.
**Causa:** la Service Account con la que corren los workers no tiene lectura del repo donde vive la imagen del Flex Template.
**Fix:** añadir un `google_artifact_registry_repository_iam_member` con `role = "roles/artifactregistry.reader"` sobre el repo y `member = "serviceAccount:<dataflow-sa>"`.

### 11. `Error: Cycle` en el grafo
**Síntoma:** `Error: Cycle: resource_a -> resource_b -> resource_a`.
**Causa:** dos recursos se referencian mutuamente (directa o indirectamente).
**Fix:** romper el ciclo con un `locals` o sacando una dependencia a `data` o a un tercer recurso/variable.

### 12. `Error: Reference to undeclared resource`
**Síntoma:** `Error: Reference to undeclared resource. A managed resource "google_x" "y" has not been declared in the root module`.
**Causa:** typo en el nombre, o el recurso vive en otro módulo que no has expuesto con `output`.
**Fix:** verifica el nombre exacto con `terraform state list` y corrige la referencia; en módulos, expón con `output "x" { value = google_x.y }` y llámalo como `module.m.x`.

### 13. `Error: Invalid for_each argument`
**Síntoma:** `The "for_each" value depends on resource attributes that cannot be determined until apply`.
**Causa:** estás iterando sobre algo `(known after apply)` — típicamente una salida de otro recurso.
**Fix:** pasar la lista por variable o hardcodear las claves; si de verdad necesitas iterar sobre un output, usa `depends_on` y `terraform apply -target` en dos pasos.

### 14. `Error: Instance cannot be destroyed`
**Síntoma:** `Resource has lifecycle.prevent_destroy set`.
**Causa:** alguien puso `lifecycle { prevent_destroy = true }` como red de seguridad.
**Fix:** si de verdad quieres destruirlo, pon `prevent_destroy = false`, `apply`, y después `destroy`.

### 15. `Error: Saved plan is stale`
**Síntoma:** `The given plan file can no longer be applied because the state was changed by another operation`.
**Causa:** entre `plan -out=…` y `apply …`, el state cambió (otro colaborador aplicó, o tú hiciste `import`).
**Fix:** vuelve a generar el plan: `terraform plan -out=…` y aplica ese.

### 16. `Error: Failed to install provider` / `checksum mismatch`
**Síntoma:** `Error: Failed to install provider. Error while installing hashicorp/google v5.45.2: checksums did not match`.
**Causa:** `.terraform.lock.hcl` tiene checksums para tu arquitectura y estás usando otra (Win→Mac, x86_64→arm64).
**Fix:** `terraform init -upgrade` (re-descarga y actualiza el lock para tu plataforma).

### 17. `Error: Error 403: The caller does not have permission`
**Síntoma:** genérico de IAM; aparece en casi cualquier recurso cuando falta un rol.
**Causa:** al usuario o a la SA le falta el rol. Ej: `storage.buckets.create` requiere `roles/storage.admin`.
**Fix:** `gcloud projects add-iam-policy-binding PROJECT --member='user:EMAIL' --role='roles/storage.admin'`. Recuerda conceder por principio de mínimo privilegio.

### 18. `terraform destroy` queda colgado en un Dataflow streaming job
**Síntoma:** `google_dataflow_flex_template_job.unified: Still destroying... […  Xm elapsed]` indefinidamente.
**Causa:** el drain del streaming job espera a procesar eventos en vuelo.
**Fix:** esperar (5-10 min es normal) o cancelar el job manualmente con `gcloud dataflow jobs cancel <JOB_ID> --region europe-west1` y dejar que Terraform lo limpie.

### 19. State drift tras cambios manuales en GCP
**Síntoma:** `terraform plan` muestra `~ update` o `- destroy / + recreate` sin que hayas cambiado `.tf`.
**Causa:** alguien tocó el recurso en la Console, haciendo `gcloud`, o GCP reescribió algo (tags de sistema, versiones…).
**Fix:** `terraform apply -refresh-only` (importa el nuevo estado sin cambiar código) o ajusta el `.tf` para reflejar la realidad.

### 20. `Error creating bucket: googleapi: Error 409: Your previous request to create the named bucket succeeded and you already own it`
**Síntoma:** típico al crear buckets GCS con nombre globalmente único.
**Causa:** el nombre ya existe en GCP (cualquier proyecto del mundo puede haberlo tomado — los nombres de bucket son globales).
**Fix:** cambia el nombre (usa prefijos con `project_id` y sufijos con hash/aleatorio).

### 21. `Error: googleapi: Error 400: The project to be billed is associated with an absent billing account`
**Síntoma:** al habilitar APIs de pago, o al crear recursos facturables.
**Causa:** el proyecto no tiene cuenta de facturación asociada, o la cuenta está cerrada.
**Fix:** `gcloud billing projects link PROJECT --billing-account=ACCOUNT_ID` o desde la Console.

### 22. `Error: googleapi: Error 403: Cloud Resource Manager API has not been used in project X before`
**Síntoma:** `Cloud Resource Manager API has not been used in project cloudrisk-492619 before or it is disabled`.
**Causa:** la API base de Terraform (`cloudresourcemanager.googleapis.com`) no está habilitada, así que Terraform ni siquiera puede consultar qué más hay.
**Fix:** `gcloud services enable cloudresourcemanager.googleapis.com` (esto lo hace `deploy.sh` en nuestro repo).

### 23. `Error: Terraform initialized in an empty directory`
**Síntoma:** `terraform init` no encuentra `.tf`.
**Causa:** estás en el directorio incorrecto o todos los ficheros acaban en `.tf.tmpl`/`.tf.bak`.
**Fix:** `cd` al directorio correcto (ej. `infrastructure/terraform/`). Verifica con `ls *.tf`.

### 24. `Error: Resource already managed by Terraform`
**Síntoma:** al importar: `Error: Resource already managed by Terraform. Resource "google_x.y" is already managed by Terraform`.
**Causa:** intentaste `terraform import` sobre algo ya en el state.
**Fix:** `terraform state list | grep y` para ver si ya está; si sí, no hace falta importar. Si no, la dirección que usas no es la correcta.

### 25. `Error: Unsupported argument` tras actualizar provider
**Síntoma:** `Error: Unsupported argument: An argument named "X" is not expected here`.
**Causa:** provider nuevo ha deprecated/renombrado un atributo (ej. `google_dataflow_flex_template_job` cambió de `parameters` obligatorio a `additional_experiments`).
**Fix:** mirar el changelog del provider y ajustar la sintaxis; fijar versión con `version = "~> 5.0"` para evitar saltos mayores accidentales.

---

## Parte 2 — Errores específicos de GCP (servicios, cuotas, auth)

### 26. `gcloud auth: Reauthentication required`
**Síntoma:** `You must re-authenticate`.
**Causa:** token de login caducado (12 h por defecto).
**Fix:** `gcloud auth login` y, para Terraform/SDKs, **además** `gcloud auth application-default login`.

### 27. `ADC not found`
**Síntoma:** Terraform/librerías Python: `google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials`.
**Causa:** nunca ejecutaste `gcloud auth application-default login`; `gcloud auth login` solo autentica el CLI, no las Application Default Credentials que usan las SDKs.
**Fix:** `gcloud auth application-default login`.

### 28. Cloud Run deploy — `Container failed to start and listen on PORT`
**Síntoma:** `Revision 'cloudrisk-api-xxxx-0001' is not ready and cannot serve traffic. The user-provided container failed to start and listen on the port defined provided by the PORT=8080 environment variable`.
**Causa:** tu app no está escuchando en `$PORT` (Cloud Run te inyecta `PORT`) o tarda más del timeout (300 s por defecto) en arrancar.
**Fix:** en FastAPI: `uvicorn main:app --host 0.0.0.0 --port $PORT`. Si el arranque es lento, subir `startup_cpu_boost` y `timeout`.

### 29. Cloud Run Job — `Image not found`
**Síntoma:** ver error 7 arriba.
**Causa:** push no ha terminado, o el tag `:latest` no se ha sobreescrito, o empujas a otro repo/región.
**Fix:** verifica con `gcloud artifacts docker images list REGION-docker.pkg.dev/PROJECT/REPO` que la imagen exista con el tag esperado. Añade `depends_on` al `null_resource` del push.

### 30. Cloud Run Job — permisos de Secret Manager
**Síntoma:** revisión arranca pero el contenedor falla con `Access to secret 'X' denied`.
**Causa:** la SA del servicio/job no tiene `roles/secretmanager.secretAccessor` sobre ese secret.
**Fix:** `google_secret_manager_secret_iam_member` con `role = "roles/secretmanager.secretAccessor"` y `member = "serviceAccount:<sa>"`.

### 31. Pub/Sub — `subscription 'X' has no subscribers`
**Síntoma:** mensajes se apilan sin consumirse; DLQ llena.
**Causa:** el subscriber (Dataflow/Cloud Run/Eventarc) no está corriendo, tiene otra subscripción, o el topic cambió.
**Fix:** revisa `gcloud pubsub subscriptions describe X` — mira el `pushConfig`/`acknowledgeDeadlineSeconds` y que coincida con el consumidor real.

### 32. Pub/Sub — DLQ sin `roles/pubsub.publisher` — mensajes bloqueados
**Síntoma:** `permission denied publishing to dead-letter topic`.
**Causa:** la SA del subscriber de la subscripción original debe poder publicar en la DLQ, y el servicio de Pub/Sub (`service-<PROJECT_NUMBER>@gcp-sa-pubsub.iam.gserviceaccount.com`) debe poder publicar en la DLQ y *subscribirse* al topic original.
**Fix:** otorgar ambos roles al SA de Pub/Sub:
```hcl
google_pubsub_topic_iam_member "dlq_pub" { role = "roles/pubsub.publisher"  … }
google_pubsub_subscription_iam_member "sub_sub" { role = "roles/pubsub.subscriber" … }
```

### 33. BigQuery streaming insert — `404 Not found: Table`
**Síntoma:** los workers de Dataflow/ingestors fallan al insertar con `Table X not found`.
**Causa:** la tabla se crea con otra convención de nombre (`dataset:table` vs `dataset.table`) o el dataset está en otra región.
**Fix:** usar el formato `PROJECT:DATASET.TABLE` (con dos puntos) en los parámetros de Dataflow; verificar región del dataset con `bq show DATASET`.

### 34. BigQuery — `Permission denied on dataset`
**Síntoma:** `User does not have bigquery.tables.create permission`.
**Causa:** faltan `roles/bigquery.dataEditor` y/o `roles/bigquery.jobUser`. `dataEditor` solo permite escribir, no correr jobs; necesitas los dos.
**Fix:** ambos roles a la SA que inserta.

### 35. Firestore — `PERMISSION_DENIED: Missing or insufficient permissions`
**Síntoma:** backend o Dataflow fallan al leer/escribir documentos.
**Causa:** la SA no tiene `roles/datastore.user` (para modo Native Firestore + compatibilidad Datastore).
**Fix:** `google_project_iam_member` con `role = "roles/datastore.user"`.

### 36. Firestore — región equivocada
**Síntoma:** `Location 'europe-west1' is not supported for Firestore Native mode`.
**Causa:** Firestore Native solo vive en regiones multirregionales (`eur3`, `nam5`) o un subset limitado de regiones.
**Fix:** cambiar la `location_id` a `eur3` (Europa) o `nam5` (US). Nuestro repo usa `eur3`.

### 37. Secret Manager — `The resource has IAM policy that prohibits public access`
**Síntoma:** `googleapi: Error 400: The request is invalid. Secret lacks an IAM binding that allows service <x> to access it`.
**Causa:** Cloud Run v2 referencia el secret con `value_source.secret_key_ref`, pero la SA del service no tiene `secretmanager.secretAccessor`.
**Fix:** añadir `google_secret_manager_secret_iam_member` sobre ese secret concreto (*nunca* a nivel proyecto, viola "least privilege").

### 38. Cloud Scheduler — `403 Permission 'run.jobs.run' denied`
**Síntoma:** el cron dispara pero el job Cloud Run no arranca.
**Causa:** el SA de Scheduler no tiene `roles/run.invoker` sobre el job concreto, o la URL del job está mal.
**Fix:** `google_cloud_run_v2_job_iam_member` con `role = "roles/run.invoker"` y `member = "serviceAccount:<scheduler-sa>"`.

### 39. Cloud Scheduler — target HTTP con Body vacío
**Síntoma:** el job arranca pero el endpoint devuelve 400/422.
**Causa:** Scheduler envía `Content-Type: application/octet-stream` y body vacío si no defines `body`. FastAPI con pydantic exige body JSON válido.
**Fix:** `body = base64encode("{}")` y `headers = { "Content-Type" = "application/json" }` en el `http_target`.

### 40. Dataflow — `Failed to read the result file: gs://.../operation_result`
**Síntoma:** job falla instantáneamente, logs solo dicen "Failed to read the result file".
**Causa:** típicamente es consecuencia de otro error (ej. `docker pull denied`). Ese error bloquea la operación antes de que se escriba el archivo de resultado.
**Fix:** revisa los logs del job (`gcloud logging read 'resource.labels.job_id="<JOB_ID>"' --severity=ERROR`) — la causa real está más arriba.

### 41. Dataflow — `JOB_STATE_FAILED` con `No space left on device` en workers
**Síntoma:** logs del worker: `OSError: [Errno 28] No space left on device`.
**Causa:** el disco temporal del worker (`temp_location`) se llenó.
**Fix:** usar workers con más disco (`disk_size_gb` en el Flex Template, o `n1-standard-4` con 100 GB por defecto). O activar `enable_streaming_engine = true` (saca los shuffles a servicio, libera disco local).

### 42. Artifact Registry — `FAILED_PRECONDITION: Permission 'artifactregistry.repositories.create' denied`
**Síntoma:** al crear el repo: denegado.
**Causa:** Compute Engine y Artifact Registry APIs no habilitadas, o al usuario le falta `roles/artifactregistry.admin`.
**Fix:** habilitar API (`gcloud services enable artifactregistry.googleapis.com`) y conceder rol.

### 43. Eventarc — `Could not create subscription` / Pub/Sub triggers
**Síntoma:** `You need roles/pubsub.admin on the project to create the subscription`.
**Causa:** Eventarc crea bajo el capó una subscripción Pub/Sub; tu usuario / SA debe poder crearla.
**Fix:** otorgar `roles/eventarc.admin` (incluye lo que necesita) o `roles/pubsub.admin` puntualmente.

### 44. IAM — `Policy update rate is exceeded`
**Síntoma:** `Error 429: Too many policy updates in a short period`.
**Causa:** Terraform está intentando aplicar muchos bindings en paralelo y GCP tiene un rate limit (~30 bindings/minuto por proyecto).
**Fix:** `terraform apply -parallelism=5` para serializar; o reorganizar bindings con `google_project_iam_binding` (uno por rol) en lugar de muchos `google_project_iam_member`.

### 45. Cloud Build — `Permission 'logging.logEntries.create' denied on resource`
**Síntoma:** `gcloud builds submit` falla con permiso denegado.
**Causa:** desde 2024 Cloud Build exige que especifiques bucket de logs O la Cloud Build SA necesita `roles/logging.logWriter`. El bucket por defecto ya no se auto-provisiona.
**Fix:** `gcloud builds submit --default-logs-bucket-behavior=REGIONAL_USER_OWNED_BUCKET --region=REGION` o concede `roles/logging.logWriter` a la Cloud Build SA.

### 46. VPC — `Quota 'ROUTES' exceeded`
**Síntoma:** al crear muchos recursos de red.
**Causa:** límite de 200 rutas/VPC (puede subirse a ~1000, pero requiere quota increase).
**Fix:** `gcloud compute project-info describe --project PROJECT | grep -A1 routes` — pedir aumento en Console > IAM > Cuotas.

### 47. Cloud SQL — `The instance could not be created because the network is not peered`
**Síntoma:** al crear Cloud SQL privado.
**Causa:** falta el peering `servicenetworking.googleapis.com` entre tu VPC y la red de Google.
**Fix:** `google_service_networking_connection` en Terraform, que establece el peering. Es un bloque recurrente olvidado.

### 48. GCS lifecycle — no borra nada
**Síntoma:** el `lifecycle_rule` de "borrar a los 7 días" se aplica pero los objetos siguen ahí.
**Causa:** la regla se evalúa una vez al día, y además "7 días" significa que el objeto **tiene** ≥ 7 días, no que se borre el día 7. A veces lifecycle está desactivado a nivel bucket (`"lifecycle": {"rule": []}` tras migraciones).
**Fix:** paciencia + verificar con `gcloud storage buckets describe gs://BUCKET --format=json | jq .lifecycle`. Si está vacío, re-aplicar Terraform.

### 49. GKE / Cloud Run auth entre servicios — `401 Unauthorized`
**Síntoma:** servicio A llama a servicio B (privado) y recibe 401.
**Causa:** el token de servicio no se adjunta. En Cloud Run-a-Cloud Run hay que pedir un ID token del metadata server (audience = URL del servicio B) y mandarlo como `Authorization: Bearer …`.
**Fix:**
```python
import google.auth.transport.requests, google.oauth2.id_token
req = google.auth.transport.requests.Request()
token = google.oauth2.id_token.fetch_id_token(req, audience=TARGET_URL)
headers = {"Authorization": f"Bearer {token}"}
```
Y dar `roles/run.invoker` a la SA de A sobre el servicio B.

### 50. Quota: `Exceeded limit 'CPUS' on resource 'europe-west1'`
**Síntoma:** Dataflow/GCE no puede arrancar VMs porque se pasa de la quota regional de CPUs.
**Causa:** cada proyecto nuevo arranca con 8-24 vCPUs por región (free tier). Dataflow con 3 workers de 4 vCPUs ya se los come.
**Fix:** pedir aumento en Console > IAM > Cuotas (suele ser automático hasta 100 vCPUs) o bajar `max_workers` en el job.

---

## Checklist — antes de abrir ticket por un error

1. `terraform version` — cumples `>= 1.8`.
2. `gcloud auth list` y `gcloud auth application-default print-access-token` responden.
3. `gcloud config get-value project` apunta al proyecto correcto.
4. APIs habilitadas: `gcloud services list --enabled | grep -E "run|firestore|pubsub|bigquery|artifactregistry|dataflow|secretmanager|cloudscheduler"`.
5. Docker corriendo: `docker info`.
6. `terraform validate` en el directorio.
7. `terraform plan -var-file=terraform.tfvars` — lee los avisos, no solo el sumario.
8. Si algo ya existe en GCP y el `plan` lo quiere crear — **import** antes de **apply**.
9. Si un `null_resource` con `local-exec` falla, ejecútalo a mano — el error de la CLI es más claro que el de Terraform.
10. Logs en GCP: `gcloud logging read 'resource.type="cloud_run_revision" severity>=ERROR' --limit=20 --freshness=1h`.
