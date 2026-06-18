from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from core.api.schemas import AddMessageRequest
from core.runtime.auth import require_api_key
from core.runtime.schemas import SessionState
from core.x_kernel.action_stager import apply_x_kernel_action_stage_to_session_state
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
        return apply_x_kernel_action_stage_to_session_state(session_state)
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
