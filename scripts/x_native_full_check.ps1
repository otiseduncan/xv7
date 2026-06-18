$ErrorActionPreference = "Stop"
$ApiBase = "http://localhost:3101"

function Assert-Field {
  param($Object, [string]$Name, $Expected)
  if ($Object.$Name -ne $Expected) {
    throw "Expected $Name=$Expected but got $($Object.$Name)"
  }
}

function Step($Name, [scriptblock]$Action) {
  Write-Host "== $Name"
  & $Action
  Write-Host "PASS: $Name"
}

function Invoke-JsonWithRetry {
  param([string]$Uri, [string]$Method = "GET", [string]$Body = "", [int]$Attempts = 12)
  for ($i = 1; $i -le $Attempts; $i++) {
    try {
      if ($Method -eq "POST") {
        return Invoke-RestMethod -Method Post -Uri $Uri -ContentType "application/json" -Body $Body
      }
      return Invoke-RestMethod $Uri
    } catch {
      if ($i -eq $Attempts) { throw }
      Start-Sleep -Seconds 2
    }
  }
}

Step "compile" {
  python -m py_compile apps\x_native_api\main.py apps\x_native_api\planner.py apps\x_native_api\diagnostics.py apps\x_native_api\stages.py apps\x_native_api\workspace.py apps\x_native_api\receipts.py apps\x_native_api\safety.py apps\x_native_api\models.py apps\x_native_api\review_bundles.py
}

Step "compose up" {
  docker compose -f docker-compose.x-native.yml up -d --build | Out-Host
}

Step "health" {
  $health = Invoke-JsonWithRetry "$ApiBase/health"
  if ($health.status -ne "ok") { throw "health failed" }
}

Step "state" {
  $state = Invoke-JsonWithRetry "$ApiBase/x-native/state"
  if ($state.status -ne "completed") { throw "state failed" }
}

Step "diagnose" {
  $body = @{ raw_text = "diagnose yourself"; operator_mode = $false } | ConvertTo-Json
  $diagnosis = Invoke-JsonWithRetry "$ApiBase/x-native/message" -Method "POST" -Body $body
  Assert-Field $diagnosis.diagnosis "execution_allowed" $false
  Assert-Field $diagnosis.diagnosis "apply_allowed" $false
  Assert-Field $diagnosis.diagnosis "repo_write" $false
}

Step "planner and review bundle" {
  $body = @{
    raw_text = "Inspect your runtime and propose the next repair needed to make this baseline production-ready. Stage only. Do not apply or write files."
    operator_mode = $false
  } | ConvertTo-Json
  $planner = Invoke-JsonWithRetry "$ApiBase/x-native/message" -Method "POST" -Body $body
  Assert-Field $planner.planner_proposal "execution_allowed" $false
  Assert-Field $planner.planner_proposal "apply_allowed" $false
  Assert-Field $planner.planner_proposal "repo_write" $false
  if (-not $planner.review_bundle.bundle_id) { throw "review bundle missing" }
}

Step "workspace draft" {
  $body = @{ path = "full-check/x_native_full_check.txt"; content = "X Native full check draft." } | ConvertTo-Json
  $draft = Invoke-JsonWithRetry "$ApiBase/x-native/workspace/draft" -Method "POST" -Body $body
  Assert-Field $draft "execution_allowed" $false
  Assert-Field $draft "apply_allowed" $false
  Assert-Field $draft "repo_write" $false
}

Step "review bundle list" {
  $latest = Invoke-JsonWithRetry "$ApiBase/x-native/review-bundles/latest"
  if ($latest.status -ne "completed") { throw "latest review bundle missing" }
  $list = Invoke-JsonWithRetry "$ApiBase/x-native/review-bundles"
  if ($list.review_bundles.Count -lt 1) { throw "review bundle list empty" }
}

Step "workspace list and UI" {
  $workspace = Invoke-JsonWithRetry "$ApiBase/x-native/workspace"
  if ($workspace.files.Count -lt 1) { throw "workspace list empty" }
  $status = (Invoke-WebRequest http://localhost:3100 -UseBasicParsing).StatusCode
  if ($status -ne 200) { throw "UI did not return 200" }
}

Step "line counts" {
  $counts = Get-ChildItem apps\x_native_api,apps\x_native_ui -Recurse -File |
    Where-Object { $_.Extension -in ".py",".js",".html",".css" } |
    ForEach-Object {
      [pscustomobject]@{ Lines = (Get-Content $_.FullName | Measure-Object -Line).Lines; Path = $_.FullName }
    } |
    Sort-Object Lines -Descending
  $counts | Format-Table | Out-Host
  $tooLarge = $counts | Where-Object { $_.Lines -gt 500 }
  if ($tooLarge) { throw "line count guardrail failed" }
}

Write-Host "X Native full check PASS"
