# XV7 — Local Run Guide

This guide covers running XV7 locally on **Windows PowerShell**.  
All commands are run from the **repo root** unless stated otherwise.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop 24+ | Must be running before launching |
| Docker Compose 2.20+ | Bundled with Docker Desktop |
| Python 3.12+ | For readiness checks and local dev; not needed for Docker-only runs |
| Ollama models | Pulled into the `xv7-ollama` container after first start |

---

## 1. Configure secrets before first launch

Docker Compose will **refuse to start** if `WEBUI_SECRET_KEY` or `CORE_API_KEY` are missing.

```powershell
# Bootstrap .env and required secrets safely
.\scripts\init_xv7_env.ps1
```

This command:

- Detects repo root automatically.
- Creates `.env` from `.env.example` when `.env` is missing.
- Ensures `WEBUI_SECRET_KEY` and `CORE_API_KEY` are valid.
- Generates missing/placeholder values without printing secret values.
- Does not overwrite valid existing values unless forced.

To intentionally rotate both required Docker secrets:

```powershell
.\scripts\init_xv7_env.ps1 -ForceRotate
```

Open `.env` and replace every `CHANGE_ME_…` placeholder:

```env
WEBUI_SECRET_KEY=<generated value>
CORE_API_KEY=<generated value>
```

**Never commit `.env` to version control.** It is already listed in `.gitignore`.

### Setting XV7_API_KEY for local dev (non-Docker)

When running the Core API directly with `uvicorn` (see [Local dev without Docker](#4-local-dev-without-docker)),
the API key is read from `XV7_API_KEY` in the current shell:

```powershell
# Set in current PowerShell session only — never persisted to a file
$env:XV7_API_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
```

### Runtime auth variable precedence (local and Docker)

XV7 uses this precedence everywhere:

1. `XV7_API_KEY` (highest priority)
2. `CORE_API_KEY` (fallback when `XV7_API_KEY` is unset)

This means either variable can protect routes, but `XV7_API_KEY` wins when both
are set. Key values are never printed by readiness output.

For Docker, keep setting `CORE_API_KEY` in `.env`; the compose stack maps it to
the app runtime key internally.

---

## 2. Pre-launch readiness check

Run the readiness script before every launch to confirm your environment is
configured:

```powershell
python scripts/check_readiness.py
```

For machine-readable output (useful in CI or shell scripts):

```powershell
python scripts/check_readiness.py --json
```

The script reports:

- Repo root detected
- Python import readiness (fastapi, uvicorn, httpx, pydantic, ollama, chromadb, aiosqlite, structlog)
- Runtime auth source: `XV7_API_KEY`, `CORE_API_KEY`, or `not_set`
- `XV7_API_KEY` — configured or not set (key is **never** printed)
- `CORE_API_KEY` — configured or not set (key is **never** printed)
- `OLLAMA_BASE_URL` — set or missing
- `XV7_MODEL_PROFILE` — set or missing
- `model_registry_file` — present or missing
- `MEMORY_DB_PATH` / `VECTOR_DB_PATH` — set or missing
- `docker-compose.yml` present

It exits **0** when all checks pass and **1** when any item needs attention.
Missing optional env vars produce warnings, not hard failures.

---

## 3. Launch the full stack (Docker Compose)

```powershell
.\scripts\start_xv7_local.ps1
```

The launcher:

1. Detects and prints the repo root.
2. Runs `python scripts/check_readiness.py` — exits if it fails (use `-SkipReadinessErrors` to continue past warnings).
3. Verifies Docker is running.
4. Runs `docker compose up -d` and writes a timestamped log to `runtime\logs\`.
5. Polls `http://localhost:8000/health` until the Core API responds (default timeout: 60 s).
6. Prints reachable endpoints.
7. Exits **1** on any failure.

Before `docker compose up -d`, the launcher validates `.env` and fails fast if
`WEBUI_SECRET_KEY` or `CORE_API_KEY` are missing/blank/placeholders. When this
preflight fails, it prints the exact variable names and tells you to run:

```powershell
.\scripts\init_xv7_env.ps1
```

### Start options

```powershell
# Default — fail on readiness issues
.\scripts\start_xv7_local.ps1

# Continue past missing optional env vars
.\scripts\start_xv7_local.ps1 -SkipReadinessErrors

# Give containers up to 2 minutes to start
.\scripts\start_xv7_local.ps1 -HealthTimeoutSeconds 120
```

### Expected endpoints after a healthy start

| Endpoint | URL | Auth required |
|---|---|---|
| Health | `http://localhost:8000/health` | No |
| Runtime status | `http://localhost:8000/runtime/status` | No |
| Runtime models | `http://localhost:8000/runtime/models` | No |
| Runtime model profiles | `http://localhost:8000/runtime/models/profiles` | No |
| Runtime active model | `http://localhost:8000/runtime/models/active` | No |
| Runtime effective model routing | `http://localhost:8000/runtime/models/effective` | No |
| Personas | `http://localhost:8000/personas` | No |
| Ollama check | `http://localhost:8000/runtime/ollama` | No |
| Open WebUI | `http://localhost:8080` | No (login required inside UI) |
| Ollama API | `http://localhost:11434` | No |

> **Port overrides:** Set `CORE_PORT`, `WEBUI_PORT`, or `OLLAMA_PORT` in `.env`
> to use different host ports.

### What the launcher does NOT claim

- It does **not** verify Ollama is reachable or that any model is loaded.  
  Check: `GET http://localhost:8000/runtime/ollama`
- It does **not** check GPU availability.
- It does **not** assert model responses will succeed.

---

## 4. Smoke test after launch

After running the launcher, run the smoke proof script:

```powershell
python scripts/smoke_xv7_local.py
```

The smoke script checks:

- `GET /health`
- `GET /runtime/status`
- `GET /runtime/ollama`
- `GET /personas`
- Protected-route auth behavior on `POST /sessions`:
  - without key must return `401` when auth is configured
  - with key header must not return `401`

The script reads host ports from environment (with defaults):

- `CORE_PORT` (default `8000`)
- `WEBUI_PORT` (default `8080`)
- `OLLAMA_PORT` (default `11434`)

The summary table uses explicit states:

- `configured`
- `reachable`
- `healthy`
- `verified`
- `not checked`
- `failed`

Exit behavior:

- Exit `0` only when all required smoke checks pass.
- Exit `1` when a required endpoint is down or auth behavior is incorrect.

Security behavior:

- API key values are never printed.
- If auth probing needs a key, the script resolves it from process env first,
  then `.env`, and always redacts printed output.

What the smoke script does NOT do in this slice:

- No browser automation.
- No model generation prompt/response checks.
- No GPU/mic/voice checks.

---

## 5. Model inventory and selection

XV7 supports multiple model roles and multiple installed Ollama models. The
active chat model is selected by configuration; it is not assumed to be the
only model present.

List installed models directly from Ollama:

```powershell
docker exec xv7-ollama ollama list
```

Run model inventory/selection proof:

```powershell
python scripts/check_ollama_models.py
```

Override active chat model for local testing (without editing code):

```powershell
$env:XV7_MODEL_PROFILE = "local_test"
python scripts/check_ollama_models.py --profile local_test
```

Or set it in `.env`:

```env
XV7_MODEL_PROFILE=local_test
```

The checker reports each role (`chat`, `embedding`, `reasoning`, `code`) with:

- `configured`
- `installed`
- `missing`
- `not checked`

Profile presets in `config/models.yml`:

- `low_resource`: `qwen3:1.7b` / `qwen3:8b` / `qwen3:8b` / `nomic-embed-text:latest`
- `balanced`: `qwen3:8b` / `qwen3:14b` / `qwen3:14b` / `nomic-embed-text:latest`
- `local_test`: `qwen3:14b` / `qwen3:14b` / `qwen3-coder:30b` / `nomic-embed-text:latest`
- `large_code`: `qwen3-coder:30b` / `qwen3:14b` / `qwen3-coder:30b` / `nomic-embed-text:latest`

Important notes:

- `EMBEDDING_MODEL` / `MODEL_EMBED` role is separate from chat selection.
- Smoke proof verifies runtime endpoints and auth behavior; it does **not**
  generate a chat response.
- `chat_model_available=false` means the configured selected chat model is not
  installed or does not match the selected tag alias.

Optional explicit pull flow (never automatic):

```powershell
python scripts/check_ollama_models.py --pull-missing
```

When used, the script prints exact model names before pulling.

### Model profile API (read-only)

XV7 now exposes read-only runtime profile discovery endpoints:

- `GET /runtime/models`
- `GET /runtime/models/profiles`
- `GET /runtime/models/active`
- `GET /runtime/models/effective`

These endpoints report:

- available profile names and role tags from `config/models.yml`
- active profile and profile source (`env`, `default`, or `override` when query override is used)
- role aliases and resolved role tags
- installed Ollama model inventory when reachable
- per-role availability for `chat`, `reasoning`, `code`, and `embedding`

Current selection source:

- Profile selection currently comes from `XV7_MODEL_PROFILE`.
- UI-driven profile selection is planned for a later slice.
- This API does not mutate profiles, write `.env`, or pull/delete models.

### Effective runtime model routing

- Raw model tags live only in `config/models.yml`.
- `GET /runtime/models/active` shows the configured active profile state.
- `GET /runtime/models/effective` shows the exact model tags runtime would use for `chat`, `reasoning`, `code`, and `embedding`.
- This endpoint is diagnostic and read-only: it does not generate text, mutate profile state, or expose secrets.
- UI model/profile selection will come in a later slice.

### Switch model profile

Use the profile switch helper to update only `XV7_MODEL_PROFILE` in `.env`:

```powershell
.\scripts\set_xv7_model_profile.ps1 -Profile balanced
```

Switch profile and recreate only the core container:

```powershell
.\scripts\set_xv7_model_profile.ps1 -Profile local_test -RestartCore
```

Preview changes without editing `.env`:

```powershell
.\scripts\set_xv7_model_profile.ps1 -Profile low_resource -DryRun
```

Notes:

- The script validates profile names from `config/models.yml`.
- It preserves all other `.env` keys and updates only `XV7_MODEL_PROFILE`.
- Profile changes affect runtime behavior after core is recreated.
- Suggested apply command: `docker compose up -d --force-recreate xv7-core`.
- UI profile selection will come in a later slice.

## 6. Pull Ollama models

After the stack starts, pull the models required by your selected profile:

```powershell
docker exec xv7-ollama ollama pull qwen3:14b
docker exec xv7-ollama ollama pull qwen3:8b
docker exec xv7-ollama ollama pull qwen3:1.7b
docker exec xv7-ollama ollama pull qwen3-coder:30b
docker exec xv7-ollama ollama pull nomic-embed-text
```

Confirm they are loaded:

```powershell
docker exec xv7-ollama ollama list
```

---

## 7. Stop the stack

```powershell
docker compose down
```

To remove volumes (wipes all data — use with caution):

```powershell
docker compose down -v
```

---

## 8. View logs

```powershell
# All services
docker compose logs -f

# Core API only
docker compose logs -f xv7-core

# Launcher output (timestamped)
Get-ChildItem runtime\logs\
```

---

## 9. Local dev without Docker

To run only the Core API (no Ollama, no WebUI):

```powershell
cd core
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# From the repo root
$env:OLLAMA_BASE_URL = "http://localhost:11434"   # point at a local Ollama install
$env:XV7_API_KEY     = "<your key>"               # optional — leave unset to disable auth

uvicorn core.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://localhost:8000`.

---

## 10. Environment variable reference

| Variable | Where used | Required | Notes |
|---|---|---|---|
| `WEBUI_SECRET_KEY` | Docker / Open WebUI | **Yes** (Docker) | Generate with `secrets.token_hex(32)` |
| `CORE_API_KEY` | Docker `.env` and runtime fallback | **Yes** (Docker) | Used when `XV7_API_KEY` is unset |
| `XV7_API_KEY` | Local uvicorn and runtime preferred key | No | Preferred key when both are set |
| `OLLAMA_BASE_URL` | Core runtime | No | Default: `http://ollama:11434` |
| `XV7_MODEL_PROFILE` | Core runtime model selection | No | Profile key from `config/models.yml` (`balanced` default) |
| `MEMORY_DB_PATH` | Core runtime | No | Default: `data/memory` |
| `VECTOR_DB_PATH` | Core runtime | No | Default: `data/vectors` |
| `CORE_PORT` | Docker | No | Default: `8000` |
| `WEBUI_PORT` | Docker | No | Default: `8080` |
| `OLLAMA_PORT` | Docker | No | Default: `11434` |

---

## 11. Troubleshooting

### docker compose up fails with "variable is not set"

Ensure `.env` exists and contains `WEBUI_SECRET_KEY` and `CORE_API_KEY`.

### Core API does not respond on port 8000

```powershell
docker compose ps
docker compose logs xv7-core
```

### Ollama models not found

```powershell
docker exec xv7-ollama ollama list
python scripts/check_ollama_models.py --profile local_test
```

### Readiness check shows import errors

Activate the correct Python virtual environment before running the script:

```powershell
.venv\Scripts\Activate.ps1
python scripts/check_readiness.py
```
