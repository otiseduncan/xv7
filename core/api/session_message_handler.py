from __future__ import annotations

from typing import Any
from uuid import UUID

from core.api.schemas import AddMessageRequest
from core.runtime.schemas import SessionState
from core.api import session_message_handler_source_01 as _source_01
from core.api import session_message_handler_source_02 as _source_02
from core.api import session_message_handler_source_03 as _source_03
from core.api import session_message_handler_source_04 as _source_04

_loaded = False


def bind_main_dependencies(module: Any) -> None:
    globals().update(vars(module))


def _load_impl() -> None:
    global _loaded
    if _loaded:
        return
    source = '\n'.join([
_source_01.SOURCE, _source_02.SOURCE, _source_03.SOURCE, _source_04.SOURCE
])
    exec(source, globals())
    _loaded = True


async def legacy_add_session_message(
    session_id: UUID,
    payload: AddMessageRequest,
    *,
    resolved_mode: str | None = None,
    kernel_plan: dict[str, Any] | None = None,
) -> SessionState:
    _load_impl()
    return await _legacy_add_session_message_impl(
        session_id,
        payload,
        resolved_mode=resolved_mode,
        kernel_plan=kernel_plan,
    )
