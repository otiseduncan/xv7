from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from core.api.schemas import (
    OperatorCancelRequest,
    OperatorConfirmRequest,
    OperatorStageRequest,
)
from core.runtime.auth import require_api_key

router = APIRouter()

_memory_manager: Any = None
_operator_manager: Any = None
_append_history: Any = None
_build_operator_history_update: Any = None
_should_clear_pending_after_confirm: Any = None
_stage_operator_response: Any = None
_operator_action_response: Any = None


def configure_operator_routes(
    *,
    memory_manager: Any,
    operator_manager: Any,
    append_history: Any,
    build_operator_history_update: Any,
    should_clear_pending_after_confirm: Any,
    stage_operator_response: Any,
    operator_action_response: Any,
) -> None:
    global _memory_manager
    global _operator_manager
    global _append_history
    global _build_operator_history_update
    global _should_clear_pending_after_confirm
    global _stage_operator_response
    global _operator_action_response

    _memory_manager = memory_manager
    _operator_manager = operator_manager
    _append_history = append_history
    _build_operator_history_update = build_operator_history_update
    _should_clear_pending_after_confirm = should_clear_pending_after_confirm
    _stage_operator_response = stage_operator_response
    _operator_action_response = operator_action_response


@router.get(
    "/operator/commands",
    dependencies=[Depends(require_api_key)],
)
async def list_operator_commands(operator_mode: bool = False) -> dict[str, Any]:
    return {
        "operator_mode": operator_mode,
        "commands": _operator_manager.list_slash_commands(operator_mode=operator_mode),
    }


@router.post(
    "/operator/stage",
    dependencies=[Depends(require_api_key)],
)
async def stage_operator_action(payload: OperatorStageRequest) -> dict[str, Any]:
    session_state = await _memory_manager.get_session(payload.session_id)
    stage_result = _operator_manager.stage_slash_command(
        payload.command_text,
        operator_mode=payload.operator_mode,
        session_metadata=session_state.metadata,
    )

    structured_receipt, _ = _build_operator_history_update(
        session_metadata=session_state.metadata,
        result=stage_result["result"],
        append_history_fn=_append_history,
    )
    await _memory_manager.update_session(session_state)

    return _stage_operator_response(
        session_id=str(payload.session_id),
        answer=stage_result["answer"],
        executed=stage_result["executed"],
        pending_action=stage_result["pending_action"],
        receipt=structured_receipt,
    )


@router.post(
    "/operator/confirm",
    dependencies=[Depends(require_api_key)],
)
async def confirm_operator_action(payload: OperatorConfirmRequest) -> dict[str, Any]:
    session_state = await _memory_manager.get_session(payload.session_id)
    pending = _operator_manager.get_pending_action(session_state.metadata)

    if pending is None or str(pending.get("action_id", "")) != payload.action_id:
        raise ValueError("No matching pending operator action found for confirmation.")

    confirmation = _operator_manager.confirm_pending_action(
        pending,
        typed_confirmation=payload.typed_confirmation,
    )
    result = confirmation["result"]
    structured_receipt, _ = _build_operator_history_update(
        session_metadata=session_state.metadata,
        result=result,
        append_history_fn=_append_history,
    )

    should_clear = _should_clear_pending_after_confirm(result)

    if should_clear:
        _operator_manager.clear_pending_action(session_state.metadata)

    await _memory_manager.update_session(session_state)

    return _operator_action_response(
        session_id=str(payload.session_id),
        answer=confirmation["answer"],
        receipt=structured_receipt,
        pending_action=_operator_manager.get_pending_action(session_state.metadata),
    )


@router.post(
    "/operator/cancel",
    dependencies=[Depends(require_api_key)],
)
async def cancel_operator_action(payload: OperatorCancelRequest) -> dict[str, Any]:
    session_state = await _memory_manager.get_session(payload.session_id)
    pending = _operator_manager.get_pending_action(session_state.metadata)

    if pending is None or str(pending.get("action_id", "")) != payload.action_id:
        raise ValueError(
            "No matching pending operator action found for cancel request."
        )

    cancellation = _operator_manager.cancel_pending_action(pending)
    _operator_manager.clear_pending_action(session_state.metadata)

    structured_receipt, _ = _build_operator_history_update(
        session_metadata=session_state.metadata,
        result=cancellation["result"],
        append_history_fn=_append_history,
    )
    await _memory_manager.update_session(session_state)

    return _operator_action_response(
        session_id=str(payload.session_id),
        answer=cancellation["answer"],
        receipt=structured_receipt,
        pending_action=None,
    )
