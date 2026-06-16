from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends

from core.api.schemas import SetActiveModelProfileRequest
from core.runtime.auth import require_api_key

router = APIRouter()

_build_runtime_status: Any = None
_fetch_ollama_status: Any = None
_fetch_ollama_status_getter: Callable[[], Any] | None = None
_fetch_runtime_models: Any = None
_fetch_runtime_models_getter: Callable[[], Any] | None = None
_build_runtime_model_profiles: Any = None
_set_runtime_profile_override: Any = None
_clear_runtime_profile_override: Any = None
_ensure_required_models_available: Any = None
_active_model_payload: Any = None
_build_effective_runtime_models: Any = None
_brain_context_manager: Any = None
_runtime_communication_proof_status_payload: Any = None


def configure_runtime_routes(
    *,
    build_runtime_status: Any,
    fetch_ollama_status: Any,
    fetch_ollama_status_getter: Callable[[], Any] | None,
    fetch_runtime_models: Any,
    fetch_runtime_models_getter: Callable[[], Any] | None,
    build_runtime_model_profiles: Any,
    set_runtime_profile_override: Any,
    clear_runtime_profile_override: Any,
    ensure_required_models_available: Any,
    active_model_payload: Any,
    build_effective_runtime_models: Any,
    brain_context_manager: Any,
    runtime_communication_proof_status_payload: Any,
) -> None:
    global _build_runtime_status
    global _fetch_ollama_status
    global _fetch_ollama_status_getter
    global _fetch_runtime_models
    global _fetch_runtime_models_getter
    global _build_runtime_model_profiles
    global _set_runtime_profile_override
    global _clear_runtime_profile_override
    global _ensure_required_models_available
    global _active_model_payload
    global _build_effective_runtime_models
    global _brain_context_manager
    global _runtime_communication_proof_status_payload

    _build_runtime_status = build_runtime_status
    _fetch_ollama_status = fetch_ollama_status
    _fetch_ollama_status_getter = fetch_ollama_status_getter
    _fetch_runtime_models = fetch_runtime_models
    _fetch_runtime_models_getter = fetch_runtime_models_getter
    _build_runtime_model_profiles = build_runtime_model_profiles
    _set_runtime_profile_override = set_runtime_profile_override
    _clear_runtime_profile_override = clear_runtime_profile_override
    _ensure_required_models_available = ensure_required_models_available
    _active_model_payload = active_model_payload
    _build_effective_runtime_models = build_effective_runtime_models
    _brain_context_manager = brain_context_manager
    _runtime_communication_proof_status_payload = (
        runtime_communication_proof_status_payload
    )


@router.get("/runtime/status")
async def runtime_status() -> dict:
    return _build_runtime_status()


@router.get("/runtime/communication-proof-status")
async def runtime_communication_proof_status() -> dict[str, Any]:
    return _runtime_communication_proof_status_payload()


@router.get("/runtime/ollama")
async def runtime_ollama() -> dict:
    if _fetch_ollama_status_getter is not None:
        return await _fetch_ollama_status_getter()()
    return await _fetch_ollama_status()


@router.get("/runtime/models")
async def runtime_models(profile: str | None = None) -> dict[str, Any]:
    if _fetch_runtime_models_getter is not None:
        return await _fetch_runtime_models_getter()(profile_override=profile)
    return await _fetch_runtime_models(profile_override=profile)


@router.get("/runtime/models/profiles")
async def runtime_model_profiles() -> dict[str, Any]:
    return _build_runtime_model_profiles()


@router.get("/runtime/models/active")
async def runtime_active_model_profile(profile: str | None = None) -> dict[str, Any]:
    if _fetch_runtime_models_getter is not None:
        payload = await _fetch_runtime_models_getter()(profile_override=profile)
    else:
        payload = await _fetch_runtime_models(profile_override=profile)
    return _active_model_payload(payload)


@router.put(
    "/runtime/models/active",
    dependencies=[Depends(require_api_key)],
)
async def set_runtime_active_model_profile(
    payload: SetActiveModelProfileRequest,
) -> dict[str, Any]:
    profiles_payload = _build_runtime_model_profiles()
    available_profiles = set(profiles_payload.get("available_profiles", []))

    _set_runtime_profile_override(payload.profile, available_profiles)

    if _fetch_runtime_models_getter is not None:
        runtime_payload = await _fetch_runtime_models_getter()()
    else:
        runtime_payload = await _fetch_runtime_models()
    if payload.require_available:
        try:
            _ensure_required_models_available(runtime_payload)
        except ValueError:
            _clear_runtime_profile_override()
            raise

    return _active_model_payload(runtime_payload)


@router.delete(
    "/runtime/models/active",
    dependencies=[Depends(require_api_key)],
)
async def clear_runtime_active_model_profile() -> dict[str, Any]:
    _clear_runtime_profile_override()
    if _fetch_runtime_models_getter is not None:
        payload = await _fetch_runtime_models_getter()()
    else:
        payload = await _fetch_runtime_models()
    return _active_model_payload(payload)


@router.get("/runtime/models/effective")
async def runtime_effective_models(profile: str | None = None) -> dict[str, Any]:
    return _build_effective_runtime_models(profile_override=profile)


@router.get("/runtime/models/artifact-connectivity")
async def runtime_artifact_model_connectivity() -> dict[str, Any]:
    return await _brain_context_manager.code_artifact_connectivity_diagnostic()


@router.get("/runtime/context/active")
async def runtime_active_context() -> dict[str, Any]:
    context = _brain_context_manager.build_active_context()
    return {
        "prompt": context.prompt,
        "receipt": context.receipt,
        "compact_receipt": context.receipt.get("compact", ""),
    }
