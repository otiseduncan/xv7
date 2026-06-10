# xv7 — Local AI Orchestration Platform

> A modular, local-first AI orchestration platform built on Docker, Ollama, and Open WebUI.  
> All inference runs on your hardware. No data leaves your machine.

---

## Architecture

```
xv7
├── core/          Python orchestration layer (FastAPI, LangChain, agents)
├── docker/        Dockerfiles for core and open-webui services
├── config/        System and model configuration (YAML)
├── public/        Static assets (3D avatars, UI elements)
├── tests/         Unit and integration tests
└── .github/       CI/CD workflows
```

**Services (Docker network: `xv7-net`)**

| Service     | Purpose                        | Default Port |
|-------------|--------------------------------|-------------|
| `ollama`    | Local LLM inference engine     | 11434       |
| `open-webui`| Browser-based chat interface   | 3000        |
| `core`      | xv7 Python orchestration API   | 8000        |

---

## Prerequisites

| Tool                  | Min Version | Notes                           |
|-----------------------|-------------|---------------------------------|
| Docker Desktop / Engine | 24+       |                                 |
| Docker Compose        | 2.20+       | Bundled with Docker Desktop     |
| NVIDIA Container Toolkit | latest   | **GPU only** — skip for CPU     |
| Python                | 3.12+       | Local dev / testing only        |

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/your-org/xv7.git
cd xv7
cp .env.example .env
```

Open `.env` and set **at minimum**:

```env
WEBUI_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
CORE_API_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
```

### 2. Start all services

```bash
# CPU mode (default)
docker compose up -d

# GPU mode — ensure nvidia-container-toolkit is installed first
docker compose up -d
```

### 3. Pull your first model

```bash
docker exec xv7-ollama ollama pull llama3.2
docker exec xv7-ollama ollama pull nomic-embed-text
```

### 4. Open the UI

Navigate to **http://localhost:3000** and create your admin account.

---

## Development

### Run Core service locally (without Docker)

```bash
cd core
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
uvicorn core.main:app --reload --port 8000
```

### Run tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

### Linting

```bash
ruff check core/
ruff format core/
mypy core/ --ignore-missing-imports
```

---

## Configuration

| File                   | Purpose                                         |
|------------------------|-------------------------------------------------|
| `.env`                 | Runtime secrets and port overrides              |
| `config/system.yml`    | App-level settings (logging, DB, cache)         |
| `config/models.yml`    | Model registry, auto-pull list, prompts         |
| `docker-compose.yml`   | Multi-container orchestration                   |

---

## Project Roadmap

- [ ] Core FastAPI app skeleton (`core/main.py`)
- [ ] Agent base class and first persona
- [ ] Memory runtime (short-term + long-term vector memory)
- [ ] 3D avatar integration in Open WebUI
- [ ] Production Helm chart / k8s manifests

---

## License

MIT — see [LICENSE](LICENSE).
