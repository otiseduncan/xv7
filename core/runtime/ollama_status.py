from __future__ import annotations

from typing import Any

import httpx

from core.runtime.model_registry import (
    configured_ollama_base_url,
    configured_ollama_timeout_seconds,
    resolve_active_models,
)


def _configured_base_url() -> str:
    return configured_ollama_base_url()


def _configured_chat_model() -> str | None:
    resolution = resolve_active_models()
    return resolution.roles.get("chat")


def _configured_embedding_model() -> str | None:
    resolution = resolve_active_models()
    return resolution.roles.get("embedding")


def _configured_timeout() -> float:
    return configured_ollama_timeout_seconds()


def _model_name(raw_model: Any) -> str | None:
    if not isinstance(raw_model, dict):
        return None

    value = raw_model.get("name") or raw_model.get("model")
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _model_matches(requested: str | None, available: str) -> bool:
    if requested is None:
        return False

    requested = requested.strip()
    available = available.strip()

    if not requested or not available:
        return False

    if requested == available:
        return True

    if ":" not in requested and available == f"{requested}:latest":
        return True

    return False


def _has_model(requested: str | None, available_models: list[str]) -> bool:
    return any(_model_matches(requested, model) for model in available_models)


async def fetch_ollama_status(
    *,
    client: httpx.AsyncClient | None = None,
    base_url: str | None = None,
    chat_model: str | None = None,
    embedding_model: str | None = None,
) -> dict[str, Any]:
    """Verify Ollama reachability and configured model visibility."""

    resolution = resolve_active_models()
    resolved_base_url = (base_url or _configured_base_url()).rstrip("/")
    resolved_chat_model = chat_model or _configured_chat_model()
    resolved_embedding_model = embedding_model or _configured_embedding_model()
    should_close_client = client is None

    if client is None:
        client = httpx.AsyncClient(timeout=_configured_timeout())

    try:
        response = await client.get(f"{resolved_base_url}/api/tags")
        response.raise_for_status()
        payload = response.json()
        raw_models = payload.get("models", [])
        if not isinstance(raw_models, list):
            raw_models = []

        available_models = sorted(
            model_name
            for model_name in (_model_name(model) for model in raw_models)
            if model_name is not None
        )

        return {
            "reachable": True,
            "base_url": resolved_base_url,
            "profile": resolution.profile,
            "profile_source": resolution.profile_source,
            "role_aliases": resolution.role_aliases,
            "resolved_models": resolution.roles,
            "chat_model": resolved_chat_model,
            "embedding_model": resolved_embedding_model,
            "models": available_models,
            "chat_model_available": _has_model(
                resolved_chat_model,
                available_models,
            ),
            "embedding_model_available": _has_model(
                resolved_embedding_model,
                available_models,
            ),
            "error": None,
            "config_error": resolution.error,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "base_url": resolved_base_url,
            "profile": resolution.profile,
            "profile_source": resolution.profile_source,
            "role_aliases": resolution.role_aliases,
            "resolved_models": resolution.roles,
            "chat_model": resolved_chat_model,
            "embedding_model": resolved_embedding_model,
            "models": [],
            "chat_model_available": False,
            "embedding_model_available": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "config_error": resolution.error,
        }
    finally:
        if should_close_client:
            await client.aclose()
