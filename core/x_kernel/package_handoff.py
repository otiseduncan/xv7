"""X Kernel package handoff helpers.

This module converts an approval-validated preview stage into a draft handoff
artifact for operator review. It does not execute, apply, enqueue, or mutate
repository files.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.x_kernel.action_stager import get_x_kernel_action_stage

RECEIPT_DIR = Path("data") / "x_inbox" / "receipts"
DRAFT_DIR = Path("data") / "x_inbox" / "drafts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "core" / "main.py").is_file():
            return candidate
    return current


def _receipt_root() -> Path:
    return _repo_root() / RECEIPT_DIR


def _draft_root() -> Path:
    return _repo_root() / DRAFT_DIR


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def _safe_stage_id(stage_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(stage_id or "").strip())
    return safe or "unknown_stage"


def _build_rendered_draft(stage: dict[str, Any], preview_package: dict[str, Any]) -> str:
    source_text = _clean_text(stage.get("source_text") or stage.get("user_request"))
    suggested_path = str(preview_package.get("suggested_path") or "data/x_runtime/tmp/operator_review_required.txt")
    return "\n".join(
        [
            "X PROMPT PACKAGE DRAFT ONLY",
            "",
            "This draft was generated from an approval-validated X Kernel stage.",
            "It is not in the executor pending queue and cannot apply by itself.",
            "",
            f"Stage ID: {stage.get('stage_id') or 'unknown'}",
            f"Source request: {source_text or 'none'}",
            "",
            "Draft X_ACTIONS outline:",
            f"CREATE_FILE_REVIEW {suggested_path}",
            "CONTENT_REQUIRED_BY_OPERATOR",
            "",
            "Safety:",
            "- draft_only: true",
            "- is_executor_ready: false",
            "- execution_allowed: false",
            "- apply_allowed: false",
            "- repo_write: false",
        ]
    )


def _build_package_draft(stage: dict[str, Any]) -> dict[str, Any]:
    preview_package = stage.get("preview_package") if isinstance(stage.get("preview_package"), dict) else {}
    source_text = _clean_text(stage.get("source_text") or stage.get("user_request"))
    suggested_path = str(preview_package.get("suggested_path") or "data/x_runtime/tmp/operator_review_required.txt")
    rendered_draft = _build_rendered_draft(stage, preview_package)
    return {
        "kind": "x_prompt_package_draft_v0",
        "stage_id": stage.get("stage_id"),
        "source_text": source_text,
        "suggested_path": suggested_path,
        "draft_only": True,
        "is_executor_ready": False,
        "execution_allowed": False,
        "apply_allowed": False,
        "requires_operator_review": True,
        "requires_operator_content": True,
        "not_in_pending_queue": True,
        "actions": [
            {
                "action_kind": "create_or_update_file_review",
                "path": suggested_path,
                "content": None,
                "content_required": True,
                "requires_operator_review": True,
            }
        ],
        "rendered_draft": rendered_draft,
    }


def prepare_x_kernel_prompt_package_handoff(
    stage_id: str,
    reason: str = "operator_requested_package_handoff",
) -> dict[str, Any]:
    """Prepare a draft package artifact from a validated preview stage.

    This writes review artifacts only under data/x_inbox/drafts and receipts.
    It does not write to data/x_inbox/pending and does not execute anything.
    """

    lookup = get_x_kernel_action_stage(stage_id)
    stage = lookup.get("stage")
    wanted_stage_id = str(stage_id or "").strip()
    if not isinstance(stage, dict):
        return {
            "receipt_type": "x_kernel_prompt_package_handoff",
            "status": "not_found",
            "stage_id": wanted_stage_id,
            "execution_allowed": False,
            "apply_allowed": False,
            "package_created": False,
        }

    if stage.get("cancelled") or stage.get("status") == "cancelled":
        return {
            "receipt_type": "x_kernel_prompt_package_handoff",
            "status": "rejected_cancelled",
            "stage_id": stage.get("stage_id"),
            "execution_allowed": False,
            "apply_allowed": False,
            "package_created": False,
            "reason": "stage_cancelled",
            "stage": stage,
        }

    if not stage.get("preview_ready") or not isinstance(stage.get("preview_package"), dict):
        return {
            "receipt_type": "x_kernel_prompt_package_handoff",
            "status": "rejected_preview_required",
            "stage_id": stage.get("stage_id"),
            "execution_allowed": False,
            "apply_allowed": False,
            "package_created": False,
            "reason": "preview_required_before_package_handoff",
            "stage": stage,
        }

    if not stage.get("approval_validated") or stage.get("status") != "approval_validated_preview_only":
        return {
            "receipt_type": "x_kernel_prompt_package_handoff",
            "status": "rejected_approval_validation_required",
            "stage_id": stage.get("stage_id"),
            "execution_allowed": False,
            "apply_allowed": False,
            "package_created": False,
            "reason": "approval_validation_required_before_package_handoff",
            "stage": stage,
        }

    package_draft = _build_package_draft(stage)
    safe_id = _safe_stage_id(str(stage.get("stage_id") or wanted_stage_id))
    draft_path = _draft_root() / f"{_stamp()}_prompt_package_draft_{safe_id}.json"
    latest_draft_path = _draft_root() / "latest_prompt_package_draft.json"

    stage_update = dict(stage)
    stage_update["status"] = "package_draft_ready"
    stage_update["package_draft_ready"] = True
    stage_update["package_handoff_requested_at"] = _utc_now()
    stage_update["package_handoff_reason"] = str(reason or "operator_requested_package_handoff")
    stage_update["package_draft_path"] = str(draft_path)
    stage_update["package_draft"] = package_draft
    stage_update["execution_allowed"] = False
    stage_update["apply_allowed"] = False
    stage_update["approval_required"] = True
    stage_update["next_step"] = "Review package_draft. A separate explicit apply flow is still required."
    stage_update["safety"] = dict(stage_update.get("safety") or {})
    stage_update["safety"].update(
        {
            "direct_execution": False,
            "repo_write": False,
            "system_control": False,
            "network_control": False,
            "package_handoff_only": True,
            "not_in_pending_queue": True,
            "note": "Package handoff creates a draft review artifact only. It does not apply or enqueue execution.",
        }
    )

    receipt = {
        "receipt_type": "x_kernel_prompt_package_handoff",
        "created_at": _utc_now(),
        "status": "package_draft_ready",
        "stage_id": stage_update.get("stage_id"),
        "package_created": True,
        "draft_only": True,
        "not_in_pending_queue": True,
        "execution_allowed": False,
        "apply_allowed": False,
        "approval_required": True,
        "draft_path": str(draft_path),
        "latest_draft_path": str(latest_draft_path),
        "package_draft": package_draft,
        "stage": stage_update,
    }

    receipts = _receipt_root()
    handoff_receipt = receipts / f"{_stamp()}_prompt_package_handoff_{safe_id}.json"
    latest_handoff = receipts / "latest_prompt_package_handoff.json"
    latest_stage = receipts / "latest_action_stage.json"

    _save_json(draft_path, package_draft)
    _save_json(latest_draft_path, package_draft)
    _save_json(handoff_receipt, receipt)
    _save_json(latest_handoff, receipt)
    _save_json(latest_stage, stage_update)

    receipt["receipt_path"] = str(handoff_receipt)
    receipt["stage"]["source_path"] = str(latest_stage)
    _save_json(handoff_receipt, receipt)
    _save_json(latest_handoff, receipt)
    return receipt
