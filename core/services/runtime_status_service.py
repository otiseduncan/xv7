from __future__ import annotations

from typing import Any


def runtime_communication_proof_status_payload() -> dict[str, Any]:
    return {
        "communication_core": "green",
        "active_focus_persistence": "green",
        "runtime_communication_proof": "green",
        "browser_receipt_visibility": "green",
        "last_completed_code": 8,
        "next_recommended_code": 9,
    }


def active_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_profile": payload["active_profile"],
        "profile_source": payload["profile_source"],
        "resolved_models": payload["resolved_models"],
        "role_aliases": payload["role_aliases"],
        "availability": payload["availability"],
        "ollama": payload["ollama"],
        "config_error": payload["config_error"],
    }


def ensure_required_models_available(runtime_payload: dict[str, Any]) -> None:
    if not runtime_payload.get("ollama", {}).get("reachable", False):
        raise ValueError(
            "Cannot apply profile with require_available=true because Ollama is unreachable."
        )

    availability = runtime_payload.get("availability", {})
    missing = [
        role
        for role in ("chat", "reasoning", "code", "embedding")
        if not bool(availability.get(role, False))
    ]
    if missing:
        raise ValueError(
            "Cannot apply profile with require_available=true; missing required "
            f"models for roles: {', '.join(missing)}."
        )
