from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from core.api.schemas import AddMessageRequest
from core.runtime.auth import require_api_key
from core.runtime.schemas import SessionState
from core.x_kernel.action_stager import (
    apply_x_kernel_action_stage_to_session_state,
    cancel_x_kernel_action_stage,
    get_latest_x_kernel_action_stage,
    get_x_kernel_action_stage,
    list_x_kernel_action_stages,
    prepare_x_kernel_action_stage_preview,
    validate_x_kernel_action_stage_approval,
)
from core.x_kernel.tool_runner import apply_x_kernel_tool_result_to_session_state

router = APIRouter()

_add_message_handler_getter: (
    Callable[[], Callable[[UUID, AddMessageRequest], Awaitable[SessionState]]] | None
) = None


def configure_session_message_routes(
    *,
    add_message_handler_getter: Callable[
        [], Callable[[UUID, AddMessageRequest], Awaitable[SessionState]]
    ],
) -> APIRouter:
    global _add_message_handler_getter
    _add_message_handler_getter = add_message_handler_getter
    return router


def _copy_session_state(session_state: SessionState, **updates: object) -> SessionState:
    """Copy a SessionState across Pydantic v1/v2 runtimes."""

    model_copy = getattr(session_state, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=updates)
    return session_state.copy(update=updates)


@router.get(
    "/x-kernel/stages",
    dependencies=[Depends(require_api_key)],
)
async def list_x_kernel_stages(limit: int = 20) -> dict[str, Any]:
    """List recent X Kernel staged-action receipts."""

    return list_x_kernel_action_stages(limit=limit)


@router.get(
    "/x-kernel/stages/latest",
    dependencies=[Depends(require_api_key)],
)
async def get_latest_x_kernel_stage() -> dict[str, Any]:
    """Return the latest X Kernel staged-action receipt."""

    return get_latest_x_kernel_action_stage()


@router.get(
    "/x-kernel/stages/{stage_id}",
    dependencies=[Depends(require_api_key)],
)
async def get_x_kernel_stage(stage_id: str) -> dict[str, Any]:
    """Return one X Kernel staged-action receipt."""

    return get_x_kernel_action_stage(stage_id)


@router.post(
    "/x-kernel/stages/{stage_id}/cancel",
    dependencies=[Depends(require_api_key)],
)
async def cancel_x_kernel_stage(
    stage_id: str,
    reason: str = "operator_cancelled",
) -> dict[str, Any]:
    """Cancel one staged action without executing it."""

    return cancel_x_kernel_action_stage(stage_id, reason=reason)


@router.post(
    "/x-kernel/stages/{stage_id}/preview",
    dependencies=[Depends(require_api_key)],
)
async def preview_x_kernel_stage(
    stage_id: str,
    reason: str = "operator_requested_preview",
) -> dict[str, Any]:
    """Prepare one staged action for preview without executing it."""

    return prepare_x_kernel_action_stage_preview(stage_id, reason=reason)


@router.post(
    "/x-kernel/stages/{stage_id}/validate-approval",
    dependencies=[Depends(require_api_key)],
)
async def validate_x_kernel_stage_approval(
    stage_id: str,
    approval_phrase: str,
    reason: str = "operator_validation_requested",
) -> dict[str, Any]:
    """Validate stage approval intent without executing or applying it."""

    return validate_x_kernel_action_stage_approval(
        stage_id,
        approval_phrase=approval_phrase,
        reason=reason,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SessionState,
    dependencies=[Depends(require_api_key)],
)
async def add_session_message_route(
    session_id: UUID,
    payload: AddMessageRequest,
) -> SessionState:
    if _add_message_handler_getter is None:
        raise RuntimeError("session message routes are not configured")
    handler = _add_message_handler_getter()
    session_state = await handler(session_id, payload)

    try:
        session_state = apply_x_kernel_tool_result_to_session_state(session_state)
    except Exception as exc:
        metadata = dict(session_state.metadata)
        metadata["x_kernel_tool_result"] = {
            "executed": False,
            "allowed": True,
            "status": "error",
            "reason": str(exc),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
        metadata["x_kernel_tool_runner"] = {
            "version": "v0",
            "mode": "allowlisted_read_only_container_native",
            "status": "error",
        }
        try:
            session_state = _copy_session_state(session_state, metadata=metadata)
        except Exception:
            return session_state

    try:
        return apply_x_kernel_action_stage_to_session_state(
            session_state,
            source_text=payload.raw_text,
        )
    except Exception as exc:
        metadata = dict(session_state.metadata)
        metadata["x_kernel_action_stage"] = {
            "executed": False,
            "allowed": False,
            "status": "error",
            "reason": str(exc),
            "approval_required": True,
            "execution_allowed": False,
        }
        metadata["x_kernel_action_stager"] = {
            "version": "v0",
            "mode": "receipt_backed_pending_approval_only",
            "status": "error",
        }
        try:
            return _copy_session_state(session_state, metadata=metadata)
        except Exception:
            return session_state
