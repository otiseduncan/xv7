"""X Kernel action staging helpers.

This module records write/control/package requests as staged plans that require
explicit future approval. It does not execute actions, apply packages, run shell
commands, or mutate repository files.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.runtime.schemas import SessionState

STAGEABLE_INTENTS = {
    "x_prompt_package",
    "repo_change_request",
    "system_control_request",
    "network_control_request",
}
STAGEABLE_RISKS = {"developer_write", "system_control", "network_control"}
SAFE_TOOL_INTENTS = {"diagnose", "readiness", "state", "proof"}
RECEIPT_DIR = Path("data") / "x_inbox" / "receipts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy_model(model: Any, **updates: Any) -> Any:
    """Copy a Pydantic model across v1/v2 runtimes."""

    model_copy = getattr(model, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=updates)
    copy = getattr(model, "copy", None)
    if callable(copy):
        return copy(update=updates)
    raise TypeError(f"Object does not support Pydantic-style copy: {type(model)!r}")


def _repo_root() -> Path:
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "core" / "main.py").is_file():
            return candidate
    return current


def _receipt_root() -> Path:
    return _repo_root() / RECEIPT_DIR


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_stage_receipt(stage: dict[str, Any]) -> tuple[Path, Path]:
    receipts = _receipt_root()
    latest = receipts / "latest_action_stage.json"
    stamped = receipts / f"{_stamp()}_action_stage.json"
    _save_json(latest, stage)
    _save_json(stamped, stage)
    return latest, stamped


def should_stage_x_kernel_action(decision: dict[str, Any]) -> bool:
    """Return true when a decision should be staged instead of executed."""

    if not isinstance(decision, dict):
        return False

    intent = str(decision.get("intent") or "")
    risk = str(decision.get("risk") or "")
    route = str(decision.get("route") or "")

    if intent in SAFE_TOOL_INTENTS and route == "tool" and risk == "developer_read":
        return False

    return (
        bool(decision.get("requires_confirmation"))
        or intent in STAGEABLE_INTENTS
        or risk in STAGEABLE_RISKS
        or route in {"prompt_inbox", "draft_package", "system_control", "network_control"}
    )


def stage_x_kernel_action(decision: dict[str, Any]) -> dict[str, Any]:
    """Create a receipt-backed pending-approval stage for a kernel decision."""

    stage_id = str(uuid4())
    stage = {
        "receipt_type": "x_kernel_action_stage",
        "created_at": _utc_now(),
        "stage_id": stage_id,
        "status": "staged_pending_approval",
        "execution_allowed": False,
        "approval_required": True,
        "approval_mode": "explicit_future_authority_flow",
        "intent": str(decision.get("intent") or "unknown"),
        "risk": str(decision.get("risk") or "unknown"),
        "route": str(decision.get("route") or "unknown"),
        "summary": str(decision.get("summary") or ""),
        "package_action": str(decision.get("package_action") or "none"),
        "command": decision.get("command") or [],
        "reasons": decision.get("reasons") or [],
        "safety": {
            "direct_execution": False,
            "repo_write": False,
            "system_control": False,
            "network_control": False,
            "note": "This stage is a plan/receipt only. A later explicit authority flow must approve execution.",
        },
        "next_step": "Review the staged plan, then approve through a dedicated authority-gated endpoint or prompt package flow.",
    }
    latest, stamped = _write_stage_receipt(stage)
    stage["receipt_path"] = str(latest)
    stage["stamped_receipt_path"] = str(stamped)
    _save_json(latest, stage)
    _save_json(stamped, stage)
    return stage


def render_action_stage(stage: dict[str, Any]) -> str:
    return (
        "Action staging:\n"
        f"Status: {stage.get('status') or 'unknown'}\n"
        f"Stage ID: {stage.get('stage_id') or 'unknown'}\n"
        f"Intent: {stage.get('intent') or 'unknown'}\n"
        f"Risk: {stage.get('risk') or 'unknown'}\n"
        f"Route: {stage.get('route') or 'unknown'}\n"
        f"Execution allowed: {stage.get('execution_allowed')}\n"
        f"Approval required: {stage.get('approval_required')}\n"
        f"Proof: {stage.get('receipt_path') or 'none'}\n\n"
        f"Next step: {stage.get('next_step') or 'Review staged plan.'}"
    )


def apply_x_kernel_action_stage_to_session_state(session_state: SessionState) -> SessionState:
    """Attach staged-action metadata and visible text to the returned SessionState."""

    decision = session_state.metadata.get("x_kernel_decision")
    if not isinstance(decision, dict):
        return session_state
    if not should_stage_x_kernel_action(decision):
        return session_state
    if session_state.metadata.get("x_kernel_action_stage"):
        return session_state
    if not session_state.messages:
        return session_state

    last_message = session_state.messages[-1]
    if last_message.role != "assistant":
        return session_state
    if last_message.metadata.get("x_kernel_action_stage"):
        return session_state

    stage = stage_x_kernel_action(decision)
    next_content = f"{last_message.content.rstrip()}\n\n{render_action_stage(stage)}"

    next_metadata = dict(last_message.metadata)
    next_metadata["x_kernel_action_stage"] = stage

    messages = list(session_state.messages)
    messages[-1] = _copy_model(last_message, content=next_content, metadata=next_metadata)

    updated_metadata = dict(session_state.metadata)
    updated_metadata["x_kernel_action_stage"] = stage
    updated_metadata["x_kernel_action_stager"] = {
        "version": "v0",
        "mode": "receipt_backed_pending_approval_only",
        "status": stage.get("status"),
    }
    return _copy_model(session_state, messages=messages, metadata=updated_metadata)
