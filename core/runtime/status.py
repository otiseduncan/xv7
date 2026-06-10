from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.runtime.model_registry import (
    configured_ollama_base_url,
    resolve_active_models,
)


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _path_from_env(name: str, default: str) -> str:
    return str(Path(os.getenv(name, default)))


def build_runtime_status() -> dict[str, Any]:
    """Return truthful runtime configuration without pretending checks passed.

    This function reports what XV7 is configured to use. It does not claim GPU,
    microphone, model, or Ollama availability unless a future verifier proves it.
    """

    resolution = resolve_active_models()

    return {
        "status": "ok",
        "platform": {
            "name": "XV7",
            "mode": "local-first",
            "cloud_fallback_enabled": _env_bool("XV7_ENABLE_CLOUD_FALLBACK", False),
        },
        "assistant": {
            "name": os.getenv("XV7_ASSISTANT_NAME", "Xoduz"),
        },
        "ollama": {
            "base_url": configured_ollama_base_url(),
            "profile": resolution.profile,
            "profile_source": resolution.profile_source,
            "chat_model": resolution.roles.get("chat"),
            "embedding_model": resolution.roles.get("embedding"),
            "reasoning_model": resolution.roles.get("reasoning"),
            "code_model": resolution.roles.get("code"),
            "role_aliases": resolution.role_aliases,
            "config_error": resolution.error,
            "verified": False,
            "verification": "not_checked",
        },
        "storage": {
            "memory_db_path": _path_from_env("MEMORY_DB_PATH", "data/memory"),
            "facts_db_path": _path_from_env(
                "FACTS_DB_PATH", "data/memory/facts.sqlite3"
            ),
            "vector_db_path": _path_from_env("VECTOR_DB_PATH", "data/vectors"),
        },
        "capabilities": {
            "gpu_verified": False,
            "microphone_verified": False,
            "voice_pipeline_verified": False,
            "synthetic_telemetry": False,
        },
    }
