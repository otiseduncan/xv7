#Requires -Version 5.1
<#
.SYNOPSIS
    Start the XV7 local runtime stack via Docker Compose.

.DESCRIPTION
    1. Detects the repo root by locating docker-compose.yml.
    2. Prints the detected path.
    3. Runs the pre-launch readiness check (scripts/check_readiness.py).
    4. Verifies Docker is running.
    5. Starts the full stack with: docker compose up -d
    6. Polls the Core API /health endpoint to confirm it is responding.
    7. Prints reachable endpoints.
    8. Exits nonzero on any failure.

    What this script does NOT claim:
    - Ollama reachability — check GET /runtime/ollama after startup.
    - Model availability — pull models with `docker exec xv7-ollama ollama pull <model>`.
    - GPU status — not probed here.

.PARAMETER SkipReadinessErrors
    Continue past readiness-check failures (e.g. unset optional env vars).
    Warnings are still printed. Required vars will still fail docker compose.

.PARAMETER HealthTimeoutSeconds
    Total seconds to wait for the Core API /health to respond.
    Default: 60. Polls every 5 seconds.

.EXAMPLE
    # From the repo root:
    .\scripts\start_xv7_local.ps1

.EXAMPLE
    # Continue even if optional env vars are missing:
    .\scripts\start_xv7_local.ps1 -SkipReadinessErrors

.EXAMPLE
    # Wait up to 2 minutes for the API to start:
    .\scripts\start_xv7_local.ps1 -HealthTimeoutSeconds 120
#>
[CmdletBinding()]
param(
    [switch]$SkipReadinessErrors,
    [int]$HealthTimeoutSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "  [OK]   $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail([string]$Message) {
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Exit-WithFailure([string]$Message) {
    Write-Fail $Message
    exit 1
}

function Normalize-EnvValue([string]$Raw) {
    if ($null -eq $Raw) {
        return $null
    }

    $value = $Raw.Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    return $value.Trim()
}

function Test-InvalidSecretValue([string]$Value) {
    $normalized = Normalize-EnvValue $Value
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $true
    }

    $lower = $normalized.ToLowerInvariant()
    if ($lower -eq 'change_me' -or $lower -eq 'changeme' -or $lower -eq 'placeholder') {
        return $true
    }

    if ($lower.Contains('change_me') -or $lower.Contains('changeme') -or $lower.Contains('placeholder')) {
        return $true
    }

    if ($normalized -eq '""' -or $normalized -eq "''") {
        return $true
    }

    return $false
}

function Read-EnvEntries([string]$Path) {
    $lines = Get-Content -Path $Path -ErrorAction Stop
    $entries = New-Object 'System.Collections.Generic.Dictionary[string,string]'

    foreach ($line in $lines) {
        $trim = $line.Trim()
        if ($trim.Length -eq 0 -or $trim.StartsWith('#')) {
            continue
        }

        $idx = $line.IndexOf('=')
        if ($idx -lt 1) {
            continue
        }

        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1)
        if (-not $entries.ContainsKey($key)) {
            $entries[$key] = $value
        }
    }

    return $entries
}

# ---------------------------------------------------------------------------
# 1. Detect repo root
# ---------------------------------------------------------------------------

Write-Step 'Detecting repo root'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot   = (Resolve-Path $scriptDir).Path

while ($repoRoot -and ($repoRoot -ne [System.IO.Path]::GetPathRoot($repoRoot))) {
    if (Test-Path (Join-Path $repoRoot 'docker-compose.yml')) {
        break
    }
    $repoRoot = Split-Path -Parent $repoRoot
}

if (-not (Test-Path (Join-Path $repoRoot 'docker-compose.yml'))) {
    Exit-WithFailure "Cannot find docker-compose.yml in any parent of $scriptDir. Run this script from inside the xv7 repo."
}

Write-Ok "Repo root: $repoRoot"
Set-Location $repoRoot

# ---------------------------------------------------------------------------
# 2. Ensure runtime/logs directory exists (for compose and API logs)
# ---------------------------------------------------------------------------

Write-Step 'Preparing runtime log directory'

$logsDir = Join-Path $repoRoot 'runtime\logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
Write-Ok "Runtime logs directory: $logsDir"

# ---------------------------------------------------------------------------
# 3. Check for .env file
# ---------------------------------------------------------------------------

Write-Step 'Checking for .env configuration file'

$envFile = Join-Path $repoRoot '.env'
if (-not (Test-Path $envFile)) {
    Write-Fail ".env not found at $envFile"
    Write-Host '  Required before launch: WEBUI_SECRET_KEY, CORE_API_KEY'
    Write-Host '  Run: .\scripts\init_xv7_env.ps1'
    exit 1
} else {
    Write-Ok ".env found: $envFile"
}

Write-Step 'Running Docker env preflight'
$entries = Read-EnvEntries $envFile
$requiredSecrets = @('WEBUI_SECRET_KEY', 'CORE_API_KEY')
$invalidNames = @()

foreach ($name in $requiredSecrets) {
    if (-not $entries.ContainsKey($name)) {
        $invalidNames += $name
        continue
    }

    if (Test-InvalidSecretValue $entries[$name]) {
        $invalidNames += $name
    }
}

if ($invalidNames.Count -gt 0) {
    Write-Fail 'Required Docker secret variables are invalid in .env:'
    foreach ($name in $invalidNames) {
        Write-Host "  - $name"
    }
    Write-Host '  Run: .\scripts\init_xv7_env.ps1'
    exit 1
}

Write-Ok 'Required Docker secret variables are valid.'

# ---------------------------------------------------------------------------
# 4. Pre-launch readiness check
# ---------------------------------------------------------------------------

Write-Step 'Running pre-launch readiness check'
Write-Host '  Command: python scripts/check_readiness.py'
Write-Host ''

& python scripts\check_readiness.py
$readinessExit = $LASTEXITCODE

Write-Host ''
if ($readinessExit -eq 0) {
    Write-Ok 'Readiness check passed.'
} elseif ($SkipReadinessErrors) {
    Write-Warn "Readiness check reported issues (exit $readinessExit). Continuing because -SkipReadinessErrors was set."
} else {
    Exit-WithFailure "Readiness check failed (exit $readinessExit). Fix the issues above, or re-run with -SkipReadinessErrors to continue anyway."
}

# ---------------------------------------------------------------------------
# 5. Verify Docker is available and the daemon is running
# ---------------------------------------------------------------------------

Write-Step 'Checking Docker availability'
Write-Host '  Command: docker info'

$dockerOutput = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Exit-WithFailure 'Docker is not running or not installed. Start Docker Desktop and retry.'
}
Write-Ok 'Docker daemon is running.'

# ---------------------------------------------------------------------------
# 6. Start the Docker Compose stack
# ---------------------------------------------------------------------------

$timestamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$composeLog = Join-Path $logsDir "compose_up_$timestamp.log"

Write-Step 'Starting XV7 Docker Compose stack'
Write-Host '  Command: docker compose up -d'
Write-Host "  Log file: $composeLog"
Write-Host ''

& docker compose up -d 2>&1 | Tee-Object -FilePath $composeLog
$composeExit = $LASTEXITCODE

Write-Host ''
if ($composeExit -ne 0) {
    Exit-WithFailure "docker compose up -d failed (exit $composeExit). Check log: $composeLog"
}
Write-Ok 'docker compose up -d succeeded.'

# ---------------------------------------------------------------------------
# 7. Resolve ports (honour env var overrides in the current shell)
# ---------------------------------------------------------------------------

$corePort   = if ($env:CORE_PORT)   { $env:CORE_PORT }   else { '8000' }
$webuiPort  = if ($env:WEBUI_PORT)  { $env:WEBUI_PORT }  else { '8080' }
$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { '11434' }

$healthUrl  = "http://localhost:$corePort/health"

# ---------------------------------------------------------------------------
# 8. Poll /health until the Core API responds
# ---------------------------------------------------------------------------

Write-Step "Waiting for Core API at $healthUrl (timeout: ${HealthTimeoutSeconds}s)"

$pollInterval = 5
$attempts     = [Math]::Ceiling($HealthTimeoutSeconds / $pollInterval)
$healthy      = $false

for ($i = 1; $i -le $attempts; $i++) {
    Write-Host "  Attempt $i/$attempts — GET $healthUrl"
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # Container still starting — keep polling
    }
    if ($i -lt $attempts) {
        Start-Sleep -Seconds $pollInterval
    }
}

if (-not $healthy) {
    Write-Warn "Core API did not respond at $healthUrl within ${HealthTimeoutSeconds}s."
    Write-Warn 'The containers may still be initialising. Check status with:'
    Write-Warn '  docker compose ps'
    Write-Warn '  docker compose logs xv7-core'
    exit 1
}

Write-Ok "Core API is responding at $healthUrl"

# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------

Write-Step 'XV7 stack started'
Write-Host ''
Write-Host "  Core API         : http://localhost:$corePort"
Write-Host "  /health          : http://localhost:$corePort/health       [verified]"
Write-Host "  /runtime/status  : http://localhost:$corePort/runtime/status"
Write-Host "  Open WebUI       : http://localhost:$webuiPort  (startup may take 20-60s)"
Write-Host "  Ollama           : http://localhost:$ollamaPort"
Write-Host ''
Write-Warn 'Ollama reachability and model availability are NOT verified here.'
Write-Warn "Check: GET http://localhost:$corePort/runtime/ollama  (requires API key if XV7_API_KEY is set)"
Write-Host ''
Write-Host '  View all logs  : docker compose logs -f'
Write-Host '  Stop the stack : docker compose down'
Write-Host "  Compose log    : $composeLog"
Write-Host ''
