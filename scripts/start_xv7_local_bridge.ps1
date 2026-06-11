param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8765,
  [string]$Token = "xv7-local-bridge-token",
  [int]$TimeoutSeconds = 10,
  [int]$MaxOutputChars = 12000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$env:PYTHONPATH = "$repoRoot"
$env:XV7_LOCAL_BRIDGE_TOKEN = $Token
$env:XV7_LOCAL_BRIDGE_TIMEOUT_SECONDS = [string]$TimeoutSeconds
$env:XV7_LOCAL_BRIDGE_MAX_OUTPUT_CHARS = [string]$MaxOutputChars
$env:XV7_LOCAL_BRIDGE_REPO_ROOT = [string]$repoRoot

Write-Host "Starting XV7 local bridge on http://$BindHost`:$Port"
Write-Host "Repo root: $repoRoot"

python -m uvicorn local_bridge.app:app --host $BindHost --port $Port
