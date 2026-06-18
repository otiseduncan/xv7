param(
  [string]$ApiBase = "http://localhost:3101"
)

$ErrorActionPreference = "Stop"

function Assert-Field {
  param(
    [Parameter(Mandatory = $true)] $Object,
    [Parameter(Mandatory = $true)] [string] $Name,
    [Parameter(Mandatory = $true)] $Expected
  )
  if ($Object.$Name -ne $Expected) {
    throw "Expected $Name=$Expected but got $($Object.$Name)"
  }
}

Write-Host "X Native smoke: $ApiBase"

$health = Invoke-RestMethod "$ApiBase/health"
if ($health.status -ne "ok") { throw "Health check failed" }
Write-Host "health: ok"

$state = Invoke-RestMethod "$ApiBase/x-native/state"
if ($state.status -ne "completed") { throw "State check failed" }
Write-Host "state: completed"

$diagnoseBody = @{ raw_text = "diagnose yourself"; operator_mode = $false } | ConvertTo-Json
$diagnosis = Invoke-RestMethod -Method Post -Uri "$ApiBase/x-native/message" -ContentType "application/json" -Body $diagnoseBody
Assert-Field $diagnosis.diagnosis "execution_allowed" $false
Assert-Field $diagnosis.diagnosis "apply_allowed" $false
Assert-Field $diagnosis.diagnosis "repo_write" $false
if ($diagnosis.diagnosis.checks.legacy_core_isolated.status -ne "pass") {
  throw "legacy_core_isolated did not pass"
}
Write-Host "diagnosis: $($diagnosis.diagnosis.status)"

$plannerBody = @{
  raw_text = "Inspect your runtime and propose the next repair needed to make this baseline production-ready. Stage only. Do not apply or write files."
  operator_mode = $false
} | ConvertTo-Json
$planner = Invoke-RestMethod -Method Post -Uri "$ApiBase/x-native/message" -ContentType "application/json" -Body $plannerBody
Assert-Field $planner.planner_proposal "execution_allowed" $false
Assert-Field $planner.planner_proposal "apply_allowed" $false
Assert-Field $planner.planner_proposal "repo_write" $false
if (-not $planner.planner_proposal.problem_summary) { throw "Planner problem_summary missing" }
Write-Host "planner: staged=$($planner.planner_proposal.staged) stage_id=$($planner.planner_proposal.stage_id)"

$workspaceBody = @{
  path = "smoke/x_native_smoke.txt"
  content = "X Native smoke workspace draft."
  stage_id = $planner.planner_proposal.stage_id
  plan = $planner.planner_proposal
} | ConvertTo-Json -Depth 8
$draft = Invoke-RestMethod -Method Post -Uri "$ApiBase/x-native/workspace/draft" -ContentType "application/json" -Body $workspaceBody
Assert-Field $draft "execution_allowed" $false
Assert-Field $draft "apply_allowed" $false
Assert-Field $draft "repo_write" $false
Assert-Field $draft "promoted_to_repo" $false
Write-Host "workspace draft: $($draft.workspace_file)"

$workspace = Invoke-RestMethod "$ApiBase/x-native/workspace"
Assert-Field $workspace "execution_allowed" $false
Assert-Field $workspace "apply_allowed" $false
Assert-Field $workspace "repo_write" $false
if ($workspace.files.Count -lt 1) { throw "Workspace list is empty" }
Write-Host "workspace files: $($workspace.files.Count)"

Write-Host "X Native smoke passed."
