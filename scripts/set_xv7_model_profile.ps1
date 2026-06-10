#Requires -Version 5.1
<#
.SYNOPSIS
    Safely switch XV7 model profile in .env without editing other keys.

.DESCRIPTION
    - Detects repo root by locating docker-compose.yml.
    - Reads profiles from config/models.yml.
    - Validates requested profile exists.
    - Updates only XV7_MODEL_PROFILE in .env.
    - Prints previous profile, new profile, and resolved role tags.
    - Prints command to apply runtime change:
      docker compose up -d --force-recreate xv7-core
    - Does not recreate containers unless -RestartCore is provided.

.PARAMETER Profile
    Target profile name from config/models.yml.
    Supported today: low_resource, balanced, local_test, large_code.

.PARAMETER RestartCore
    Recreate only xv7-core after updating .env.

.PARAMETER DryRun
    Show what would change without writing .env or restarting containers.

.EXAMPLE
    .\scripts\set_xv7_model_profile.ps1 -Profile balanced

.EXAMPLE
    .\scripts\set_xv7_model_profile.ps1 -Profile local_test -RestartCore

.EXAMPLE
    .\scripts\set_xv7_model_profile.ps1 -Profile low_resource -DryRun
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Profile,
    [switch]$RestartCore,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "  [OK]   $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Exit-WithFailure([string]$Message) {
    Write-Fail $Message
    exit 1
}

function Find-RepoRoot([string]$StartPath) {
    $current = (Resolve-Path $StartPath).Path
    while ($current -and ($current -ne [System.IO.Path]::GetPathRoot($current))) {
        if (Test-Path (Join-Path $current 'docker-compose.yml')) {
            return $current
        }
        $current = Split-Path -Parent $current
    }

    if ($current -and (Test-Path (Join-Path $current 'docker-compose.yml'))) {
        return $current
    }

    return $null
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

    return @{
        lines = $lines
        entries = $entries
    }
}

function Set-EnvValueInLines([string[]]$Lines, [string]$Key, [string]$Value) {
    $updated = $false
    $output = New-Object System.Collections.Generic.List[string]

    foreach ($line in $Lines) {
        $trimmed = $line.TrimStart()
        if ($trimmed.StartsWith('#')) {
            $output.Add($line)
            continue
        }

        $idx = $line.IndexOf('=')
        if ($idx -lt 1) {
            $output.Add($line)
            continue
        }

        $candidate = $line.Substring(0, $idx).Trim()
        if ($candidate -eq $Key) {
            $output.Add("${Key}=${Value}")
            $updated = $true
        }
        else {
            $output.Add($line)
        }
    }

    if (-not $updated) {
        $output.Add("${Key}=${Value}")
    }

    return ,$output.ToArray()
}

function Get-ProfileMap([string]$ModelsPath) {
    $pythonCode = @'
import json
import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:
    raise SystemExit(f"YAML loader unavailable: {exc}")

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"models file not found: {path}")

parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
registry = parsed.get("registry") or {}
profiles = registry.get("profiles") or {}

out = {}
for profile_name, role_map in profiles.items():
    if not isinstance(profile_name, str):
        continue
    if not isinstance(role_map, dict):
        continue

    out[profile_name] = {
        "chat": role_map.get("chat"),
        "reasoning": role_map.get("reasoning"),
        "code": role_map.get("code"),
        "embedding": role_map.get("embedding"),
    }

print(json.dumps(out))
'@

    $json = & python -c $pythonCode $ModelsPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        Exit-WithFailure "Failed reading config/models.yml: $json"
    }

    try {
        $parsed = $json | ConvertFrom-Json -AsHashtable
    }
    catch {
        Exit-WithFailure "Failed parsing profile data from config/models.yml"
    }

    if ($null -eq $parsed) {
        return @{}
    }

    return $parsed
}

Write-Step 'Detecting repo root'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Find-RepoRoot $scriptDir
if ($null -eq $repoRoot) {
    Exit-WithFailure "Cannot find docker-compose.yml in any parent directory of $scriptDir."
}
Write-Ok "Repo root: $repoRoot"

$envPath = Join-Path $repoRoot '.env'
if (-not (Test-Path $envPath)) {
    Exit-WithFailure ".env not found at $envPath. Run .\scripts\init_xv7_env.ps1 first."
}

$modelsPath = Join-Path $repoRoot 'config\models.yml'
$profiles = Get-ProfileMap $modelsPath
if (-not $profiles.ContainsKey($Profile)) {
    $known = ($profiles.Keys | Sort-Object) -join ', '
    Exit-WithFailure "Unknown profile '$Profile'. Available profiles: $known"
}

$envData = Read-EnvEntries $envPath
$lines = [string[]]$envData.lines
$entries = $envData.entries

$previousProfile = '<not_set>'
if ($entries.ContainsKey('XV7_MODEL_PROFILE')) {
    $normalized = Normalize-EnvValue $entries['XV7_MODEL_PROFILE']
    if (-not [string]::IsNullOrWhiteSpace($normalized)) {
        $previousProfile = $normalized
    }
}

$selected = $profiles[$Profile]
$chatTag = [string](Normalize-EnvValue $selected['chat'])
$reasoningTag = [string](Normalize-EnvValue $selected['reasoning'])
$codeTag = [string](Normalize-EnvValue $selected['code'])
$embeddingTag = [string](Normalize-EnvValue $selected['embedding'])

Write-Step 'Switch summary'
Write-Host "  Previous profile: $previousProfile"
Write-Host "  New profile:      $Profile"
Write-Host "  Resolved role tags:"
Write-Host "    chat:      $chatTag"
Write-Host "    reasoning: $reasoningTag"
Write-Host "    code:      $codeTag"
Write-Host "    embedding: $embeddingTag"

$updatedLines = Set-EnvValueInLines -Lines $lines -Key 'XV7_MODEL_PROFILE' -Value $Profile

if ($DryRun) {
    Write-Ok 'Dry run enabled; .env was not modified.'
}
elseif ($PSCmdlet.ShouldProcess($envPath, "Set XV7_MODEL_PROFILE=$Profile")) {
    Set-Content -Path $envPath -Value $updatedLines -Encoding UTF8
    Write-Ok '.env updated (XV7_MODEL_PROFILE only).'
}

Write-Host "  Apply command: docker compose up -d --force-recreate xv7-core"

if ($RestartCore) {
    if ($DryRun) {
        Write-Ok 'Dry run enabled; xv7-core was not recreated.'
    }
    elseif ($PSCmdlet.ShouldProcess('xv7-core', 'docker compose up -d --force-recreate xv7-core')) {
        Push-Location $repoRoot
        try {
            docker compose up -d --force-recreate xv7-core
            if ($LASTEXITCODE -ne 0) {
                Exit-WithFailure 'Failed to recreate xv7-core container.'
            }
        }
        finally {
            Pop-Location
        }
        Write-Ok 'xv7-core recreated.'
    }
}
else {
    Write-Ok 'Core container not restarted. Recreate when you want profile changes applied.'
}
