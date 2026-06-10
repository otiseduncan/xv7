"""Local runtime readiness reporter for XV7.

Checks what the runtime is *configured* to use and reports it clearly.
Does NOT probe live services (Ollama, Docker) — that would require network
access and is out of scope for a pre-launch checklist.  Missing / unconfigured
items are reported as warnings, never as silent defaults.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ReadinessItem:
    """One line in the readiness report."""

    key: str
    value: str
    ok: bool
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "ok": self.ok,
            "warning": self.warning,
        }


@dataclass
class ReadinessReport:
    """Aggregated result of all readiness checks."""

    items: list[ReadinessItem] = field(default_factory=list)

    def add(self, item: ReadinessItem) -> None:
        self.items.append(item)

    @property
    def warnings(self) -> list[str]:
        return [i.warning for i in self.items if i.warning is not None]

    @property
    def all_ok(self) -> bool:
        return all(i.ok for i in self.items)

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [i.as_dict() for i in self.items],
            "warnings": self.warnings,
            "all_ok": self.all_ok,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "ollama",
    "chromadb",
    "aiosqlite",
    "structlog",
]


def _module_available(name: str) -> bool:
    """Return True if *name* can be imported in the current environment."""
    return importlib.util.find_spec(name) is not None


def _find_repo_root(start: Path | None = None) -> Path | None:
    """Walk upward from *start* (or CWD) looking for docker-compose.yml / .git."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "docker-compose.yml").exists() or (candidate / ".git").exists():
            return candidate
    return None


def _env_str(name: str) -> str:
    """Return the stripped value of an env var, or empty string."""
    return os.getenv(name, "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_readiness_report(repo_root: Path | None = None) -> ReadinessReport:
    """Build and return a :class:`ReadinessReport` for the local environment.

    Args:
        repo_root: Override the repo root instead of auto-detecting it.
                   Useful for tests.

    Returns:
        A populated :class:`ReadinessReport` with items and warnings.
        No live service probes are performed.
    """
    report = ReadinessReport()

    # ------------------------------------------------------------------
    # 1. Repo root
    # ------------------------------------------------------------------
    detected_root = repo_root if repo_root is not None else _find_repo_root()
    if detected_root is not None:
        report.add(
            ReadinessItem(
                key="repo_root",
                value=str(detected_root),
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="repo_root",
                value="not_detected",
                ok=False,
                warning=(
                    "Could not detect repo root — no docker-compose.yml or .git "
                    "found in any parent directory."
                ),
            )
        )

    # ------------------------------------------------------------------
    # 2. Python import readiness
    # ------------------------------------------------------------------
    for pkg in _REQUIRED_PACKAGES:
        available = _module_available(pkg)
        report.add(
            ReadinessItem(
                key=f"import:{pkg}",
                value="available" if available else "missing",
                ok=available,
                warning=(
                    None
                    if available
                    else f"Required package '{pkg}' is not importable in this environment."
                ),
            )
        )

    # ------------------------------------------------------------------
    # 3. API key
    # ------------------------------------------------------------------
    api_key = _env_str("XV7_API_KEY")
    if api_key:
        report.add(
            ReadinessItem(
                key="XV7_API_KEY",
                value="configured",  # never print the actual key
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="XV7_API_KEY",
                value="not_set",
                ok=False,
                warning=(
                    "XV7_API_KEY is not set — protected routes will be unguarded "
                    "when the server starts."
                ),
            )
        )

    # ------------------------------------------------------------------
    # 4. Ollama base URL
    # ------------------------------------------------------------------
    ollama_url = _env_str("OLLAMA_BASE_URL")
    if ollama_url:
        report.add(
            ReadinessItem(
                key="OLLAMA_BASE_URL",
                value=ollama_url,
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="OLLAMA_BASE_URL",
                value="not_set",
                ok=False,
                warning="OLLAMA_BASE_URL is not set; runtime will fall back to http://ollama:11434.",
            )
        )

    # ------------------------------------------------------------------
    # 5. Model names
    # ------------------------------------------------------------------
    model_default = _env_str("MODEL_DEFAULT")
    if model_default:
        report.add(
            ReadinessItem(
                key="MODEL_DEFAULT",
                value=model_default,
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="MODEL_DEFAULT",
                value="not_set",
                ok=False,
                warning="MODEL_DEFAULT is not set; runtime will fall back to llama3.",
            )
        )

    embedding_model = _env_str("EMBEDDING_MODEL")
    if embedding_model:
        report.add(
            ReadinessItem(
                key="EMBEDDING_MODEL",
                value=embedding_model,
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="EMBEDDING_MODEL",
                value="not_set",
                ok=False,
                warning="EMBEDDING_MODEL is not set; runtime will fall back to nomic-embed-text.",
            )
        )

    # ------------------------------------------------------------------
    # 6. Memory / vector paths
    # ------------------------------------------------------------------
    memory_path = _env_str("MEMORY_DB_PATH")
    if memory_path:
        report.add(
            ReadinessItem(
                key="MEMORY_DB_PATH",
                value=memory_path,
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="MEMORY_DB_PATH",
                value="not_set",
                ok=False,
                warning="MEMORY_DB_PATH is not set; runtime will fall back to data/memory.",
            )
        )

    vector_path = _env_str("VECTOR_DB_PATH")
    if vector_path:
        report.add(
            ReadinessItem(
                key="VECTOR_DB_PATH",
                value=vector_path,
                ok=True,
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="VECTOR_DB_PATH",
                value="not_set",
                ok=False,
                warning="VECTOR_DB_PATH is not set; runtime will fall back to data/vectors.",
            )
        )

    # ------------------------------------------------------------------
    # 7. Docker Compose file
    # ------------------------------------------------------------------
    if detected_root is not None:
        compose_path = detected_root / "docker-compose.yml"
        compose_present = compose_path.exists()
        report.add(
            ReadinessItem(
                key="docker_compose_present",
                value=str(compose_path) if compose_present else "not_found",
                ok=compose_present,
                warning=(
                    None
                    if compose_present
                    else f"docker-compose.yml not found at {detected_root}."
                ),
            )
        )
    else:
        report.add(
            ReadinessItem(
                key="docker_compose_present",
                value="unknown",
                ok=False,
                warning="Cannot verify docker-compose.yml — repo root was not detected.",
            )
        )

    return report
