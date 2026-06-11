# CODE-09 — CI Parity Gate Prompt

## Purpose

Stop GitHub Actions from becoming the first place failures are discovered.

CODE-09 adds a local gate that mirrors the GitHub CI environment closely enough to catch predictable failures before push.

## Problem being solved

The repeated CI failure showed the risk:

- local Windows tests passed
- GitHub Linux/Python tests failed
- the failing assertion was environment-dependent
- the repo needed a Linux/Python parity check before push

The fix is not more guessing. The fix is a documented, runnable local CI gate.

## Required implementation

Add a local script:

```text
scripts/ci-gate.ps1
```

The script must run from the repo root and must fail fast with clear output.

It should run, at minimum:

```powershell
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
python -m mypy core/ --ignore-missing-imports
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
npm test -- public/app.test.js
docker build -f docker/core/Dockerfile .
docker build -f docker/open-webui/Dockerfile .
docker compose config
```

## Linux/Python parity mode

Add an optional Docker-backed Linux gate:

```text
scripts/ci-gate-linux.ps1
```

It should use a Python 3.12 container to approximate GitHub Actions:

```powershell
docker run --rm `
  -v "${PWD}:/workspace" `
  -w /workspace `
  python:3.12-slim `
  bash -lc "python -m pip install --upgrade pip && python -m pip install -r core/requirements.txt ruff mypy pytest pytest-asyncio && python -m ruff check core/ tests/ && python -m ruff format --check core/ tests/ && python -m mypy core/ --ignore-missing-imports && PYTHONPATH=/workspace python -m pytest tests/ -v --tb=short --asyncio-mode=auto"
```

If dependencies differ from the actual workflow, inspect `.github/workflows/ci.yml` and align this script to the real workflow.

## Optional pre-push hook

Add:

```text
scripts/install-pre-push-hook.ps1
```

The hook should run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci-gate.ps1
```

The hook must be opt-in. Do not silently install it.

## Operator behavior

When Otis asks:

- "is it safe to push?"
- "run the gate"
- "check CI parity"
- "do we have a green push?"

Xoduz should know the workflow:

1. inspect git status
2. run local gate
3. run Linux parity gate if Docker is available
4. report exactly which checks passed/failed
5. do not say green unless every required command passed

## Acceptance tests

Add tests or script checks proving:

1. `scripts/ci-gate.ps1` exists.
2. `scripts/ci-gate-linux.ps1` exists.
3. the scripts do not require secrets.
4. the scripts do not mutate source files.
5. the scripts fail non-zero if a command fails.
6. the scripts print a final compact summary.

## Done means

CODE-09 is done when Otis can run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci-gate.ps1
```

and get a clear local answer before pushing.

The goal is simple:

```text
No more GitHub as the first test runner.
```
