from __future__ import annotations

import os
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
    render_action_stage,
    should_stage_x_kernel_action,
    stage_x_kernel_action,
    validate_x_kernel_action_stage_approval,
)
from core.x_kernel.decision import XDecisionKernel
from core.x_kernel.package_draft_content import attach_operator_content_to_package_draft
from core.x_kernel.package_draft_review import (
    get_latest_x_kernel_prompt_package_draft,
    get_x_kernel_prompt_package_draft,
    list_x_kernel_prompt_package_drafts,
)
from core.x_kernel.package_handoff import prepare_x_kernel_prompt_package_handoff
from core.x_kernel.tool_runner import (
    apply_x_kernel_tool_result_to_session_state,
    render_tool_result,
    run_x_kernel_tool,
)

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
    "/x-kernel/messages",
    dependencies=[Depends(require_api_key)],
)
async def x_kernel_direct_message(payload: AddMessageRequest) -> dict[str, Any]:
    """Handle one X Kernel UI message without the legacy session-visible bridge.

    This endpoint is the browser control-panel path. It directly returns the
    receipt-backed safe tool output for read-only intents or a staged action for
    write/control intents. It does not run model inference, shell commands, or
    unrestricted repo mutation.
    """

    raw_text = str(payload.raw_text or "")
    try:
        decision = XDecisionKernel().decide(raw_text).to_dict()
    except Exception as exc:
        decision = {
            "intent": "kernel_error",
            "risk": "none",
            "route": "answer_only",
            "summary": str(exc),
            "requires_confirmation": False,
            "command": [],
            "package_action": "none",
            "reasons": ["x_kernel_exception"],
        }

    response: dict[str, Any] = {
        "receipt_type": "x_kernel_direct_message",
        "status": "completed",
        "content": "",
        "x_kernel_decision": decision,
        "metadata": {
            "x_kernel_decision": decision,
            "x_kernel_ui_route": "direct_receipt_backed_v0",
        },
        "execution_allowed": False,
        "apply_allowed": False,
    }

    if should_stage_x_kernel_action(decision):
        stage = stage_x_kernel_action(decision, source_text=raw_text)
        content = render_action_stage(stage)
        response["content"] = content
        response["x_kernel_action_stage"] = stage
        response["metadata"]["x_kernel_action_stage"] = stage
        return response

    tool_result = run_x_kernel_tool(decision)
    content = (
        "X Kernel direct tool response.\n\n"
        f"Intent: {decision.get('intent') or 'unknown'}\n"
        f"Risk: {decision.get('risk') or 'unknown'}\n"
        f"Route: {decision.get('route') or 'unknown'}\n\n"
        f"{render_tool_result(tool_result)}"
    )
    response["content"] = content
    response["x_kernel_tool_result"] = tool_result
    response["metadata"]["x_kernel_tool_result"] = tool_result
    response["metadata"]["x_kernel_tool_runner"] = {
        "version": "v0",
        "mode": "direct_ui_allowlisted_receipt_backed",
        "status": tool_result.get("status"),
    }
    return response


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
    "/x-kernel/stages/{stage_id}/prepare-package",
    dependencies=[Depends(require_api_key)],
)
async def prepare_x_kernel_stage_package(
    stage_id: str,
    reason: str = "operator_requested_package_handoff",
) -> dict[str, Any]:
    """Prepare a draft prompt-package handoff without enqueueing or applying it."""

    return prepare_x_kernel_prompt_package_handoff(stage_id, reason=reason)


@router.get(
    "/x-kernel/package-drafts",
    dependencies=[Depends(require_api_key)],
)
async def list_x_kernel_package_drafts(limit: int = 20) -> dict[str, Any]:
    """List package draft review artifacts without applying them."""

    return list_x_kernel_prompt_package_drafts(limit=limit)


@router.get(
    "/x-kernel/package-drafts/latest",
    dependencies=[Depends(require_api_key)],
)
async def get_latest_x_kernel_package_draft() -> dict[str, Any]:
    """Return the latest package draft review artifact."""

    return get_latest_x_kernel_prompt_package_draft()


@router.get(
    "/x-kernel/package-drafts/{stage_id}",
    dependencies=[Depends(require_api_key)],
)
async def get_x_kernel_package_draft(stage_id: str) -> dict[str, Any]:
    """Return one package draft review artifact by stage id."""

    return get_x_kernel_prompt_package_draft(stage_id)


@router.post(
    "/x-kernel/package-drafts/{stage_id}/attach-content",
    dependencies=[Depends(require_api_key)],
)
async def attach_x_kernel_package_draft_content(
    stage_id: str,
    payload: dict[str, Any],
    reason: str = "operator_attached_content",
) -> dict[str, Any]:
    """Attach operator content to a package draft without enqueueing or applying it."""

    content = payload.get("content") if isinstance(payload, dict) else ""
    return attach_operator_content_to_package_draft(
        stage_id,
        content=str(content or ""),
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
    return await handler(session_id, payload)
