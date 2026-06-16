from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from core.api.schemas import AddMessageRequest
from core.runtime.auth import require_api_key
from core.runtime.schemas import SessionState

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
    return await handler(session_id, payload)
