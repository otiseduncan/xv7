from __future__ import annotations

from typing import Any

import httpx

from core.runtime.model_registry import (
    load_registry_config,
    resolve_active_models,
    resolve_model_for_runtime_role,
)
from core.runtime.ollama_status import fetch_ollama_status


def _public_profile_source(source: str) -> str:
    if source == "registry_default":
        return "default"
    return source


def _profiles_payload(raw_profiles: Any) -> dict[str, dict[str, str | None]]:
    if not isinstance(raw_profiles, dict):
        return {}

    profiles: dict[str, dict[str, str | None]] = {}
    for profile_name, profile_data in raw_profiles.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            continue
        if not isinstance(profile_data, dict):
            continue

        profiles[profile_name] = {
            "chat": _clean_role_tag(profile_data.get("chat")),
            "reasoning": _clean_role_tag(profile_data.get("reasoning")),
            "code": _clean_role_tag(profile_data.get("code")),
            "embedding": _clean_role_tag(profile_data.get("embedding")),
        }

    return profiles


def _clean_role_tag(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def build_runtime_model_profiles(
    *,
    profile_override: str | None = None,
) -> dict[str, Any]:
    config = load_registry_config()
    profiles = _profiles_payload(config.registry.get("profiles"))
    resolution = resolve_active_models(profile_override=profile_override)

    return {
        "available_profiles": sorted(profiles.keys()),
        "profiles": profiles,
        "active_profile": resolution.profile,
        "profile_source": _public_profile_source(resolution.profile_source),
        "role_aliases": resolution.role_aliases,
        "resolved_models": resolution.roles,
        "config_error": resolution.error,
    }


async def fetch_runtime_models(
    *,
    profile_override: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    profile_payload = build_runtime_model_profiles(profile_override=profile_override)
    ollama_payload = await fetch_ollama_status(
        client=client,
        profile_override=profile_override,
    )

    return {
        **profile_payload,
        "availability": ollama_payload.get(
            "role_model_availability",
            {
                "chat": False,
                "reasoning": False,
                "code": False,
                "embedding": False,
            },
        ),
        "ollama": {
            "reachable": ollama_payload.get("reachable", False),
            "base_url": ollama_payload.get("base_url"),
            "models": ollama_payload.get("models", []),
            "error": ollama_payload.get("error"),
        },
    }


def build_effective_runtime_models(
    *,
    profile_override: str | None = None,
) -> dict[str, Any]:
    profile_payload = build_runtime_model_profiles(profile_override=profile_override)

    effective_chat = resolve_model_for_runtime_role("chat", profile=profile_override)
    effective_reasoning = resolve_model_for_runtime_role(
        "reasoning", profile=profile_override
    )
    effective_code = resolve_model_for_runtime_role("code", profile=profile_override)
    effective_embedding = resolve_model_for_runtime_role(
        "embedding", profile=profile_override
    )

    return {
        "active_profile": profile_payload["active_profile"],
        "profile_source": profile_payload["profile_source"],
        "effective_models": {
            "chat": effective_chat.model_tag,
            "reasoning": effective_reasoning.model_tag,
            "code": effective_code.model_tag,
            "embedding": effective_embedding.model_tag,
        },
        "role_resolutions": {
            "chat": {
                "alias_used": effective_chat.alias_used,
                "canonical_role": effective_chat.canonical_role,
                "model_tag": effective_chat.model_tag,
            },
            "reasoning": {
                "alias_used": effective_reasoning.alias_used,
                "canonical_role": effective_reasoning.canonical_role,
                "model_tag": effective_reasoning.model_tag,
            },
            "code": {
                "alias_used": effective_code.alias_used,
                "canonical_role": effective_code.canonical_role,
                "model_tag": effective_code.model_tag,
            },
            "embedding": {
                "alias_used": effective_embedding.alias_used,
                "canonical_role": effective_embedding.canonical_role,
                "model_tag": effective_embedding.model_tag,
            },
        },
        "role_aliases": profile_payload["role_aliases"],
        "config_error": profile_payload["config_error"],
    }
