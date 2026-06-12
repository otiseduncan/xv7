$ErrorActionPreference = 'Stop'

Set-Location (Split-Path -Parent $PSScriptRoot)
$repoRoot = (Get-Location).Path -replace '\\', '/'

function Invoke-CiStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "== $Title =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Title (exit code $LASTEXITCODE)"
    }
}

function Invoke-Python312 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    docker run --rm `
        -e PYTHONPATH=/work `
        -v "${repoRoot}:/work" `
        -w /work `
        python:3.12-slim `
        sh -lc $Command
}

Write-Host '== XV7 local CI mirror =='

Invoke-CiStep -Title 'Lint & Type Check' -Command {
    Invoke-Python312 'python -m pip install ruff mypy && python -m ruff check core/ && python -m ruff format --check core/ && python -m mypy core/ --ignore-missing-imports'
}

Invoke-CiStep -Title 'Unit & Integration Tests' -Command {
    Invoke-Python312 'python -m pip install -r core/requirements.txt && python -m pytest tests/ -v --tb=short --asyncio-mode=auto'
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is required to mirror the GitHub Actions build jobs locally.'
}

Invoke-CiStep -Title 'Docker build core image' -Command {
    docker build -f docker/core/Dockerfile -t xv7-local-core .
}

Invoke-CiStep -Title 'Docker build open-webui image' -Command {
    docker build -f docker/open-webui/Dockerfile -t xv7-local-open-webui .
}

Invoke-CiStep -Title 'Git status' -Command {
    git status --short
}