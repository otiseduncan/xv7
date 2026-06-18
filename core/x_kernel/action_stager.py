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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_stage_receipt(stage: dict[str, Any]) -> tuple[Path, Path]:
    receipts = _receipt_root()
    latest = receipts / "latest_action_stage.json"
    stamped = receipts / f"{_stamp()}_action_stage.json"
    _save_json(latest, stage)
    _save_json(stamped, stage)
    return latest, stamped


def _clean_source_text(source_text: str | None) -> str:
    text = str(source_text or "").strip()
    if len(text) > 4000:
        return text[:4000] + "\n...[truncated]"
    return text


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


def stage_x_kernel_action(
    decision: dict[str, Any],
    source_text: str | None = None,
) -> dict[str, Any]:
    """Create a receipt-backed pending-approval stage for a kernel decision."""

    stage_id = str(uuid4())
    clean_source_text = _clean_source_text(
        source_text
        or str(decision.get("source_text") or decision.get("user_request") or "")
    )
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
        "source_text": clean_source_text,
        "user_request": clean_source_text,
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
    source_text = str(stage.get("source_text") or "").strip()
    source_line = f"Source request: {source_text}\n" if source_text else ""
    return (
        "Action staging:\n"
        f"Status: {stage.get('status') or 'unknown'}\n"
        f"Stage ID: {stage.get('stage_id') or 'unknown'}\n"
        f"Intent: {stage.get('intent') or 'unknown'}\n"
        f"Risk: {stage.get('risk') or 'unknown'}\n"
        f"Route: {stage.get('route') or 'unknown'}\n"
        f"{source_line}"
        f"Execution allowed: {stage.get('execution_allowed')}\n"
        f"Approval required: {stage.get('approval_required')}\n"
        f"Proof: {stage.get('receipt_path') or 'none'}\n\n"
        f"Next step: {stage.get('next_step') or 'Review staged plan.'}"
    )


def _stage_receipt_files() -> list[Path]:
    receipts = _receipt_root()
    if not receipts.is_dir():
        return []
    files = [path for path in receipts.glob("*_action_stage.json") if path.name != "latest_action_stage.json"]
    return sorted(files, key=lambda path: path.name, reverse=True)


def _latest_stage_or_none() -> dict[str, Any] | None:
    latest = _receipt_root() / "latest_action_stage.json"
    if not latest.is_file():
        return None
    stage = _load_json(latest)
    stage.setdefault("source_path", str(latest))
    return stage


def _load_stage_file(path: Path) -> dict[str, Any] | None:
    try:
        stage = _load_json(path)
    except Exception:
        return None
    stage.setdefault("source_path", str(path))
    return stage


def list_x_kernel_action_stages(limit: int = 20) -> dict[str, Any]:
    """Return recent staged-action receipts without executing anything.

    Latest state takes precedence over older stamped receipts so cancellation or
    preview-preparation status cannot be hidden by an older pending receipt.
    """

    safe_limit = max(1, min(int(limit or 20), 100))
    stages: list[dict[str, Any]] = []
    seen: set[str] = set()

    latest = _latest_stage_or_none()
    if isinstance(latest, dict):
        stage_id = str(latest.get("stage_id") or "")
        if stage_id:
            stages.append(latest)
            seen.add(stage_id)

    for path in _stage_receipt_files():
        stage = _load_stage_file(path)
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("stage_id") or "")
        if stage_id in seen:
            continue
        stages.append(stage)
        if stage_id:
            seen.add(stage_id)
        if len(stages) >= safe_limit:
            break

    return {
        "receipt_type": "x_kernel_action_stage_list",
        "status": "completed",
        "count": len(stages[:safe_limit]),
        "limit": safe_limit,
        "stages": stages[:safe_limit],
        "execution_allowed": False,
    }


def get_latest_x_kernel_action_stage() -> dict[str, Any]:
    """Return the latest staged-action receipt, if present."""

    latest = _latest_stage_or_none()
    if not isinstance(latest, dict):
        return {
            "receipt_type": "x_kernel_action_stage_latest",
            "status": "not_found",
            "stage": None,
            "execution_allowed": False,
        }
    return {
        "receipt_type": "x_kernel_action_stage_latest",
        "status": "completed",
        "stage": latest,
        "execution_allowed": False,
    }


def get_x_kernel_action_stage(stage_id: str) -> dict[str, Any]:
    """Return one staged-action receipt by stage id, if present.

    Latest state is checked first so cancellation or preview-preparation status
    wins over older stamped stage receipts.
    """

    wanted = str(stage_id or "").strip()
    if not wanted:
        return {"status": "not_found", "stage": None, "execution_allowed": False}

    latest = _latest_stage_or_none()
    if isinstance(latest, dict) and str(latest.get("stage_id") or "") == wanted:
        return {
            "receipt_type": "x_kernel_action_stage_lookup",
            "status": "completed",
            "stage": latest,
            "execution_allowed": False,
        }

    for path in _stage_receipt_files():
        stage = _load_stage_file(path)
        if not isinstance(stage, dict):
            continue
        if str(stage.get("stage_id") or "") == wanted:
            return {
                "receipt_type": "x_kernel_action_stage_lookup",
                "status": "completed",
                "stage": stage,
                "execution_allowed": False,
            }
    return {
        "receipt_type": "x_kernel_action_stage_lookup",
        "status": "not_found",
        "stage": None,
        "execution_allowed": False,
    }


def cancel_x_kernel_action_stage(stage_id: str, reason: str = "operator_cancelled") -> dict[str, Any]:
    """Cancel a staged action without executing it."""

    lookup = get_x_kernel_action_stage(stage_id)
    stage = lookup.get("stage")
    if not isinstance(stage, dict):
        return {
            "receipt_type": "x_kernel_action_stage_cancel",
            "status": "not_found",
            "stage_id": str(stage_id or ""),
            "execution_allowed": False,
            "cancelled": False,
        }

    cancelled = dict(stage)
    cancelled["status"] = "cancelled"
    cancelled["cancelled"] = True
    cancelled["cancelled_at"] = _utc_now()
    cancelled["cancel_reason"] = str(reason or "operator_cancelled")
    cancelled["execution_allowed"] = False
    cancelled["approval_required"] = False
    cancelled["next_step"] = "Stage cancelled. Create a new staged plan if action is still needed."

    receipts = _receipt_root()
    cancel_receipt = receipts / f"{_stamp()}_action_stage_cancel_{cancelled.get('stage_id')}.json"
    latest_cancel = receipts / "latest_action_stage_cancel.json"
    latest_stage = receipts / "latest_action_stage.json"
    _save_json(cancel_receipt, cancelled)
    _save_json(latest_cancel, cancelled)
    _save_json(latest_stage, cancelled)

    return {
        "receipt_type": "x_kernel_action_stage_cancel",
        "status": "cancelled",
        "stage_id": cancelled.get("stage_id"),
        "cancelled": True,
        "execution_allowed": False,
        "approval_required": False,
        "receipt_path": str(cancel_receipt),
        "stage": cancelled,
    }


def prepare_x_kernel_action_stage_preview(
    stage_id: str,
    reason: str = "operator_requested_preview",
) -> dict[str, Any]:
    """Mark a staged action as ready for preview without executing it."""

    lookup = get_x_kernel_action_stage(stage_id)
    stage = lookup.get("stage")
    if not isinstance(stage, dict):
        return {
            "receipt_type": "x_kernel_action_stage_preview",
            "status": "not_found",
            "stage_id": str(stage_id or ""),
            "execution_allowed": False,
            "preview_ready": False,
        }

    if stage.get("cancelled") or stage.get("status") == "cancelled":
        return {
            "receipt_type": "x_kernel_action_stage_preview",
            "status": "rejected_cancelled",
            "stage_id": stage.get("stage_id"),
            "execution_allowed": False,
            "preview_ready": False,
            "reason": "stage_cancelled",
            "stage": stage,
        }

    preview = dict(stage)
    preview["status"] = "preview_ready"
    preview["preview_ready"] = True
    preview["preview_only"] = True
    preview["preview_requested_at"] = _utc_now()
    preview["preview_reason"] = str(reason or "operator_requested_preview")
    preview["execution_allowed"] = False
    preview["approval_required"] = True
    preview["next_step"] = "Generate or inspect a preview package. A separate explicit apply flow is still required."
    preview["safety"] = dict(preview.get("safety") or {})
    preview["safety"].update(
        {
            "direct_execution": False,
            "repo_write": False,
            "system_control": False,
            "network_control": False,
            "preview_only": True,
            "note": "Preview preparation does not execute, apply, or mutate repository files.",
        }
    )

    receipts = _receipt_root()
    preview_receipt = receipts / f"{_stamp()}_action_stage_preview_{preview.get('stage_id')}.json"
    latest_preview = receipts / "latest_action_stage_preview.json"
    latest_stage = receipts / "latest_action_stage.json"
    _save_json(preview_receipt, preview)
    _save_json(latest_preview, preview)
    _save_json(latest_stage, preview)

    return {
        "receipt_type": "x_kernel_action_stage_preview",
        "status": "preview_ready",
        "stage_id": preview.get("stage_id"),
        "preview_ready": True,
        "preview_only": True,
        "execution_allowed": False,
        "approval_required": True,
        "receipt_path": str(preview_receipt),
        "stage": preview,
    }


def apply_x_kernel_action_stage_to_session_state(
    session_state: SessionState,
    source_text: str | None = None,
) -> SessionState:
    """Attach staged-action metadata and replace visible text with the authority stage receipt."""

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

    stage = stage_x_kernel_action(decision, source_text=source_text)
    next_content = render_action_stage(stage)

    next_metadata = dict(last_message.metadata)
    next_metadata["x_kernel_action_stage"] = stage
    next_metadata["x_kernel_visible_override"] = "action_stage_authoritative"

    messages = list(session_state.messages)
    messages[-1] = _copy_model(last_message, content=next_content, metadata=next_metadata)

    updated_metadata = dict(session_state.metadata)
    updated_metadata["x_kernel_action_stage"] = stage
    updated_metadata["x_kernel_visible_override"] = "action_stage_authoritative"
    updated_metadata["x_kernel_action_stager"] = {
        "version": "v0",
        "mode": "receipt_backed_pending_approval_only",
        "status": stage.get("status"),
    }
    return _copy_model(session_state, messages=messages, metadata=updated_metadata)
