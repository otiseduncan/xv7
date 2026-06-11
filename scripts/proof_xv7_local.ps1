#Requires -Version 5.1
<#!
.SYNOPSIS
    Run the known-good local XV7 launch proof.

.DESCRIPTION
    Executes the two-step operator proof flow:
    1) .\scripts\start_xv7_local.ps1
    2) python scripts/operator_readiness_report.py

    Exits nonzero if either step fails.

.PARAMETER SkipReadinessErrors
    Passed through to start_xv7_local.ps1.

.PARAMETER HealthTimeoutSeconds
    Passed through to start_xv7_local.ps1.

.PARAMETER Profile
    Profile passed to operator_readiness_report.py (default: local_test).

.PARAMETER SkipChatProof
    Passed through to operator_readiness_report.py.

.PARAMETER Json
    Output operator report as JSON.
#>
[CmdletBinding()]
param(
    [switch]$SkipReadinessErrors,
    [int]$HealthTimeoutSeconds = 60,
    [string]$Profile = 'local_test',
    [switch]$SkipChatProof,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path

Set-Location $repoRoot

Write-Host "==> Step 1/2: Launch stack" -ForegroundColor Cyan
& .\scripts\start_xv7_local.ps1 -SkipReadinessErrors:$SkipReadinessErrors -HealthTimeoutSeconds $HealthTimeoutSeconds
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Launch failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "" 
Write-Host "==> Step 2/2: Operator readiness proof" -ForegroundColor Cyan
$reportArgs = @('scripts/operator_readiness_report.py', '--profile', $Profile)
if ($SkipChatProof) {
    $reportArgs += '--skip-chat-proof'
}
if ($Json) {
    $reportArgs += '--json'
}

& python @reportArgs
$reportExit = $LASTEXITCODE
if ($reportExit -ne 0) {
    Write-Host "  [FAIL] Operator readiness proof failed." -ForegroundColor Red
    exit $reportExit
}

Write-Host "" 
Write-Host "  [OK] Known-good launch proof passed." -ForegroundColor Green
exit 0
