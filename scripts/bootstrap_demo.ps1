<#
.SYNOPSIS
  Bootstrap CloudRISK demo data (Windows PowerShell wrapper).

.DESCRIPTION
  Tras `terraform apply`, corre este script para tener la demo lista:
    - 4 jugadores, 87 zonas, 38 ya conquistadas, histórico de batallas.
    - 4 mensajes ejemplo en Pub/Sub para que Dataflow escriba en BQ.

  Delega en sembrar_demo.py (Python, cross-platform). Este wrapper
  solo verifica Python + gcloud + deps y llama al .py con tus args.

.PARAMETER Project
  ID del proyecto GCP. Si no se pasa, usa `$env:PROJECT_ID` o el valor
  de `gcloud config get-value project`.

.PARAMETER DryRun
  Imprime qué haría sin tocar nada.

.PARAMETER NoPubSub
  Salta la publicación de mensajes de ejemplo.

.EXAMPLE
  .\scripts\bootstrap_demo.ps1 -Project cloudrisk-492619

.EXAMPLE
  .\scripts\bootstrap_demo.ps1 -Project cloudrisk-492619 -DryRun
#>

[CmdletBinding()]
param(
    [string]$Project = $env:PROJECT_ID,
    [switch]$DryRun,
    [switch]$NoPubSub,
    [switch]$NoFirestore
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent $scriptDir

function Write-Ok($msg)   { Write-Host "  " -NoNewline; Write-Host "✓" -ForegroundColor Green -NoNewline; Write-Host " $msg" }
function Write-Info($msg) { Write-Host "  " -NoNewline; Write-Host "→" -ForegroundColor Blue  -NoNewline; Write-Host " $msg" }
function Write-Err($msg)  { Write-Host "  " -NoNewline; Write-Host "✗" -ForegroundColor Red   -NoNewline; Write-Host " $msg" }
function Write-Section($title) { Write-Host ""; Write-Host "━━ $title ━━" -ForegroundColor Cyan }

Write-Section "Pre-flight checks"

# 1. Python
$pythonBin = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $pythonBin = $candidate
        break
    }
}
if (-not $pythonBin) {
    Write-Err "Python 3 no encontrado. Instálalo desde https://python.org (marca 'Add to PATH')."
    exit 1
}
$pyVersion = & $pythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Ok "Python $pyVersion en $pythonBin"

# 2. gcloud (si no usas emuladores)
$usingEmulators = $env:FIRESTORE_EMULATOR_HOST -or $env:PUBSUB_EMULATOR_HOST
if (-not $usingEmulators) {
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        Write-Err "gcloud no encontrado. Instálalo: https://cloud.google.com/sdk/docs/install"
        exit 1
    }
    Write-Ok "gcloud presente"

    # ADC
    try {
        & gcloud auth application-default print-access-token 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "no ADC" }
        Write-Ok "Application Default Credentials presentes"
    } catch {
        Write-Err "Sin Application Default Credentials. Corre: gcloud auth application-default login"
        exit 1
    }
} else {
    Write-Info "Emulators en uso → saltando verificación gcloud"
}

# 3. Project ID
if (-not $Project) {
    try {
        $Project = (& gcloud config get-value project 2>$null).Trim()
    } catch {}
}
if (-not $Project) {
    Write-Err "No se pudo determinar PROJECT_ID. Pásalo con -Project <id> o exporta `$env:PROJECT_ID"
    exit 1
}
Write-Ok "Project: $Project"

# 4. Python deps
Write-Section "Python deps"
& $pythonBin -c "import google.cloud.firestore, google.cloud.pubsub_v1, passlib" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "Instalando google-cloud-firestore + google-cloud-pubsub + passlib[bcrypt]..."
    & $pythonBin -m pip install --quiet --user google-cloud-firestore google-cloud-pubsub 'passlib[bcrypt]'
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install falló. Corre manualmente: $pythonBin -m pip install google-cloud-firestore google-cloud-pubsub 'passlib[bcrypt]'"
        exit 1
    }
}
Write-Ok "deps listas"

# 5. Launch
Write-Section "Launching sembrar_demo.py"
$pyArgs = @(
    (Join-Path $scriptDir "sembrar_demo.py"),
    "--project", $Project
)
if ($DryRun)      { $pyArgs += "--dry-run" }
if ($NoPubSub)    { $pyArgs += "--no-pubsub" }
if ($NoFirestore) { $pyArgs += "--no-firestore" }

& $pythonBin @pyArgs
exit $LASTEXITCODE
