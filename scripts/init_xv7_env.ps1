#Requires -Version 5.1
<#
.SYNOPSIS
    Bootstrap and validate required XV7 Docker secrets in .env.

.DESCRIPTION
    - Detects repo root by locating docker-compose.yml.
    - Creates .env from .env.example if missing.
    - Ensures WEBUI_SECRET_KEY and CORE_API_KEY are present and valid.
    - Generates missing/invalid secrets without printing secret values.
    - Does not rotate valid existing secrets unless -ForceRotate is set.

.PARAMETER ForceRotate
    Rotate WEBUI_SECRET_KEY and CORE_API_KEY even when valid values exist.

.EXAMPLE
    .\scripts\init_xv7_env.ps1

.EXAMPLE
    .\scripts\init_xv7_env.ps1 -ForceRotate
#>
[CmdletBinding()]
param(
    [switch]$ForceRotate
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

function New-SecretValue {
    try {
        $py = (& python -c "import secrets; print(secrets.token_hex(32))" 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $candidate = ("$py").Trim()
            if ($candidate -match '^[0-9a-f]{64}$') {
                return $candidate
            }
        }
    }
    catch {
        # fall through to PowerShell fallback
    }

    try {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        return ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
    }
    catch {
        Exit-WithFailure 'Failed to generate secure random secret with both Python and PowerShell fallback.'
    }
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
    $updated = @()
    $written = $false

    foreach ($line in $Lines) {
        $idx = $line.IndexOf('=')
        if ($idx -gt 0) {
            $lineKey = $line.Substring(0, $idx).Trim()
            if ($lineKey -eq $Key) {
                if (-not $written) {
                    $updated += "$Key=$Value"
                    $written = $true
                }
                else {
                    $updated += $line
                }
                continue
            }
        }
        $updated += $line
    }

    if (-not $written) {
        $updated += "$Key=$Value"
    }

    return ,$updated
}

function Ensure-SecretValue(
    [string]$Name,
    [string]$CurrentValue,
    [bool]$Exists,
    [switch]$Rotate
) {
    $valid = $false
    if ($Exists) {
        $valid = -not (Test-InvalidSecretValue $CurrentValue)
    }

    if ($Rotate) {
        if ($Exists) {
            return @{ status = 'rotated'; value = (New-SecretValue) }
        }
        return @{ status = 'created'; value = (New-SecretValue) }
    }

    if ($Exists -and $valid) {
        return @{ status = 'already present'; value = (Normalize-EnvValue $CurrentValue) }
    }

    return @{ status = 'created'; value = (New-SecretValue) }
}

Write-Step 'Detecting repo root'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Find-RepoRoot $scriptDir
if ($null -eq $repoRoot) {
    Exit-WithFailure "Cannot find docker-compose.yml in any parent directory of $scriptDir."
}
Write-Ok "Repo root: $repoRoot"

$envPath = Join-Path $repoRoot '.env'
$envExamplePath = Join-Path $repoRoot '.env.example'

if (-not (Test-Path $envPath)) {
    Write-Step 'Creating .env from .env.example'
    if (-not (Test-Path $envExamplePath)) {
        Exit-WithFailure ".env is missing and .env.example was not found at $envExamplePath"
    }
    Copy-Item -Path $envExamplePath -Destination $envPath -Force
    Write-Ok '.env file status: created'
}
else {
    Write-Ok '.env file status: already present'
}

Write-Step 'Ensuring required Docker secrets'

$data = Read-EnvEntries $envPath
$lines = [string[]]$data.lines
$entries = $data.entries

$required = @('WEBUI_SECRET_KEY', 'CORE_API_KEY')

foreach ($name in $required) {
    $exists = $entries.ContainsKey($name)
    $current = if ($exists) { $entries[$name] } else { $null }

    $result = Ensure-SecretValue -Name $name -CurrentValue $current -Exists:$exists -Rotate:$ForceRotate
    $status = [string]$result.status
    $value = [string]$result.value

    if ($status -eq 'already present') {
        Write-Host "  ${name}: already present"
        continue
    }

    $lines = Set-EnvValueInLines -Lines $lines -Key $name -Value $value
    $entries[$name] = $value

    if ($status -eq 'created') {
        Write-Host "  ${name}: created"
    }
    elseif ($status -eq 'rotated') {
        Write-Host "  ${name}: rotated"
    }
    else {
        Write-Host "  ${name}: skipped"
    }
}

Set-Content -Path $envPath -Value $lines -Encoding UTF8

Write-Ok 'Secret bootstrap complete.'
exit 0
