from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from core.api.schemas import AddMessageRequest
from core.runtime.auth import require_api_key
from core.runtime.schemas import SessionState
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
        return apply_x_kernel_tool_result_to_session_state(session_state)
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
            "mode": "allowlisted_read_only_direct_functions",
            "status": "error",
        }
        try:
            return _copy_session_state(session_state, metadata=metadata)
        except Exception:
            return session_state
