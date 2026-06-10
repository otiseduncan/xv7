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
# Copy the template
Copy-Item .env.example .env

# Generate secret values (run each; paste the output into .env)
python -c "import secrets; print(secrets.token_hex(32))"
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

> **Note:** In Docker mode, the container reads `CORE_API_KEY` from `.env`.
> The environment variable name differs between the two modes.
> This is a known gap; a future slice will align them.

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
- `XV7_API_KEY` — configured or not set (key is **never** printed)
- `OLLAMA_BASE_URL` — set or missing
- `MODEL_DEFAULT` / `EMBEDDING_MODEL` — set or missing
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

## 4. Pull Ollama models

After the stack starts, pull the models defined in `.env`:

```powershell
docker exec xv7-ollama ollama pull llama3
docker exec xv7-ollama ollama pull nomic-embed-text
```

Confirm they are loaded:

```powershell
docker exec xv7-ollama ollama list
```

---

## 5. Stop the stack

```powershell
docker compose down
```

To remove volumes (wipes all data — use with caution):

```powershell
docker compose down -v
```

---

## 6. View logs

```powershell
# All services
docker compose logs -f

# Core API only
docker compose logs -f xv7-core

# Launcher output (timestamped)
Get-ChildItem runtime\logs\
```

---

## 7. Local dev without Docker

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

## 8. Environment variable reference

| Variable | Where used | Required | Notes |
|---|---|---|---|
| `WEBUI_SECRET_KEY` | Docker / Open WebUI | **Yes** (Docker) | Generate with `secrets.token_hex(32)` |
| `CORE_API_KEY` | Docker / Core container | **Yes** (Docker) | Protects Core API in Docker mode |
| `XV7_API_KEY` | Local uvicorn | No | Protects Core API in local dev mode |
| `OLLAMA_BASE_URL` | Core runtime | No | Default: `http://ollama:11434` |
| `MODEL_DEFAULT` | Core runtime | No | Default: `llama3` |
| `EMBEDDING_MODEL` | Core runtime | No | Default: `nomic-embed-text` |
| `MEMORY_DB_PATH` | Core runtime | No | Default: `data/memory` |
| `VECTOR_DB_PATH` | Core runtime | No | Default: `data/vectors` |
| `CORE_PORT` | Docker | No | Default: `8000` |
| `WEBUI_PORT` | Docker | No | Default: `8080` |
| `OLLAMA_PORT` | Docker | No | Default: `11434` |

---

## 9. Troubleshooting

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
docker exec xv7-ollama ollama pull llama3
```

### Readiness check shows import errors

Activate the correct Python virtual environment before running the script:

```powershell
.venv\Scripts\Activate.ps1
python scripts/check_readiness.py
```
