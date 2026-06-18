"""Attach operator-reviewed content to X Kernel package drafts.

This module updates draft review artifacts only under data/x_inbox/drafts and
writes receipts under data/x_inbox/receipts. It does not enqueue, execute,
apply, or mutate repository target files.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.x_kernel.package_draft_review import get_x_kernel_prompt_package_draft

DRAFT_DIR = Path("data") / "x_inbox" / "drafts"
RECEIPT_DIR = Path("data") / "x_inbox" / "receipts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "core" / "main.py").is_file():
            return candidate
    return current


def _draft_root() -> Path:
    return _repo_root() / DRAFT_DIR


def _receipt_root() -> Path:
    return _repo_root() / RECEIPT_DIR


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_text(value: Any, limit: int = 20000) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def _safe_stage_id(stage_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(stage_id or "").strip())
    return safe or "unknown_stage"


def _render_content_attached_draft(draft: dict[str, Any], content: str) -> str:
    stage_id = str(draft.get("stage_id") or "unknown_stage")
    source_text = _clean_text(draft.get("source_text"), limit=4000)
    suggested_path = str(draft.get("suggested_path") or "data/x_runtime/tmp/operator_review_required.txt")
    content_preview = _clean_text(content, limit=12000)
    return "\n".join(
        [
            "X PROMPT PACKAGE DRAFT WITH OPERATOR CONTENT",
            "",
            "This draft has operator-provided content attached for review.",
            "It is still not in the executor pending queue and cannot apply by itself.",
            "",
            f"Stage ID: {stage_id}",
            f"Source request: {source_text or 'none'}",
            "",
            "Draft X_ACTIONS outline:",
            f"CREATE_FILE_REVIEW {suggested_path}",
            "CONTENT_ATTACHED_FOR_REVIEW",
            "",
            "Attached content preview:",
            content_preview or "[empty]",
            "",
            "Safety:",
            "- draft_only: true",
            "- content_attached: true",
            "- is_executor_ready: false",
            "- execution_allowed: false",
            "- apply_allowed: false",
            "- not_in_pending_queue: true",
        ]
    )


def attach_operator_content_to_package_draft(
    stage_id: str,
    content: str,
    reason: str = "operator_attached_content",
) -> dict[str, Any]:
    """Attach operator-reviewed content to a package draft without applying it."""

    wanted_stage_id = str(stage_id or "").strip()
    safe_id = _safe_stage_id(wanted_stage_id)
    cleaned_content = _clean_text(content)

    if not cleaned_content:
        return {
            "receipt_type": "x_kernel_prompt_package_draft_content",
            "status": "rejected_empty_content",
            "stage_id": wanted_stage_id,
            "content_attached": False,
            "execution_allowed": False,
            "apply_allowed": False,
            "not_in_pending_queue": True,
            "reason": "operator_content_required",
        }

    lookup = get_x_kernel_prompt_package_draft(wanted_stage_id)
    draft = lookup.get("draft") if isinstance(lookup, dict) else None
    if not isinstance(draft, dict):
        return {
            "receipt_type": "x_kernel_prompt_package_draft_content",
            "status": "not_found",
            "stage_id": wanted_stage_id,
            "content_attached": False,
            "execution_allowed": False,
            "apply_allowed": False,
            "not_in_pending_queue": True,
        }

    updated_draft = dict(draft)
    actions = updated_draft.get("actions") if isinstance(updated_draft.get("actions"), list) else []
    updated_actions: list[dict[str, Any]] = []
    for action in actions:
        if isinstance(action, dict):
            next_action = dict(action)
            next_action["content"] = cleaned_content
            next_action["content_required"] = False
            next_action["content_attached"] = True
            next_action["requires_operator_review"] = True
            updated_actions.append(next_action)
    if not updated_actions:
        updated_actions.append(
            {
                "action_kind": "create_or_update_file_review",
                "path": str(updated_draft.get("suggested_path") or "data/x_runtime/tmp/operator_review_required.txt"),
                "content": cleaned_content,
                "content_required": False,
                "content_attached": True,
                "requires_operator_review": True,
            }
        )

    updated_draft.update(
        {
            "status": "content_attached_review_only",
            "content_attached": True,
            "content_attached_at": _utc_now(),
            "content_attachment_reason": str(reason or "operator_attached_content"),
            "requires_operator_content": False,
            "requires_operator_review": True,
            "draft_only": True,
            "review_only": True,
            "not_in_pending_queue": True,
            "is_executor_ready": False,
            "execution_allowed": False,
            "apply_allowed": False,
            "actions": updated_actions,
        }
    )
    updated_draft["rendered_draft"] = _render_content_attached_draft(updated_draft, cleaned_content)

    draft_path = _draft_root() / f"{_stamp()}_prompt_package_draft_content_{safe_id}.json"
    latest_draft_path = _draft_root() / "latest_prompt_package_draft.json"
    receipt_path = _receipt_root() / f"{_stamp()}_prompt_package_draft_content_{safe_id}.json"
    latest_receipt_path = _receipt_root() / "latest_prompt_package_draft_content.json"

    receipt = {
        "receipt_type": "x_kernel_prompt_package_draft_content",
        "created_at": _utc_now(),
        "status": "content_attached_review_only",
        "stage_id": wanted_stage_id,
        "content_attached": True,
        "draft_only": True,
        "review_only": True,
        "not_in_pending_queue": True,
        "is_executor_ready": False,
        "execution_allowed": False,
        "apply_allowed": False,
        "draft_path": str(draft_path),
        "latest_draft_path": str(latest_draft_path),
        "draft": updated_draft,
    }

    _save_json(draft_path, updated_draft)
    _save_json(latest_draft_path, updated_draft)
    _save_json(receipt_path, receipt)
    _save_json(latest_receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    receipt["draft"]["source_path"] = str(draft_path)
    _save_json(receipt_path, receipt)
    _save_json(latest_receipt_path, receipt)
    return receipt
