"""Read-only X Kernel package draft review helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DRAFT_DIR = Path("data") / "x_inbox" / "drafts"


def _repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "core" / "main.py").is_file():
            return candidate
    return current


def _draft_root() -> Path:
    return _repo_root() / DRAFT_DIR


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _draft_files() -> list[Path]:
    root = _draft_root()
    if not root.exists():
        return []
    files = [path for path in root.glob("*_prompt_package_draft_*.json") if path.is_file()]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def _normalize(payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    draft = dict(payload)
    draft.setdefault("source_path", str(source_path))
    draft["draft_only"] = True
    draft["review_only"] = True
    draft["is_executor_ready"] = False
    draft["execution_allowed"] = False
    draft["apply_allowed"] = False
    draft["not_in_pending_queue"] = True
    return draft


def list_x_kernel_prompt_package_drafts(limit: int = 20) -> dict[str, Any]:
    try:
        wanted = max(1, min(int(limit), 50))
    except Exception:
        wanted = 20
    drafts: list[dict[str, Any]] = []
    for path in _draft_files()[:wanted]:
        payload = _load_json(path)
        if payload is not None:
            drafts.append(_normalize(payload, path))
    return {
        "receipt_type": "x_kernel_prompt_package_draft_list",
        "status": "completed",
        "count": len(drafts),
        "limit": wanted,
        "drafts": drafts,
        "execution_allowed": False,
        "apply_allowed": False,
        "not_in_pending_queue": True,
    }


def get_latest_x_kernel_prompt_package_draft() -> dict[str, Any]:
    latest_path = _draft_root() / "latest_prompt_package_draft.json"
    payload = _load_json(latest_path)
    if payload is not None:
        return {
            "receipt_type": "x_kernel_prompt_package_draft_latest",
            "status": "completed",
            "draft": _normalize(payload, latest_path),
            "execution_allowed": False,
            "apply_allowed": False,
            "not_in_pending_queue": True,
        }
    listed = list_x_kernel_prompt_package_drafts(limit=1)
    drafts = listed.get("drafts") if isinstance(listed.get("drafts"), list) else []
    if drafts:
        return {
            "receipt_type": "x_kernel_prompt_package_draft_latest",
            "status": "completed",
            "draft": drafts[0],
            "execution_allowed": False,
            "apply_allowed": False,
            "not_in_pending_queue": True,
        }
    return {
        "receipt_type": "x_kernel_prompt_package_draft_latest",
        "status": "not_found",
        "draft": None,
        "execution_allowed": False,
        "apply_allowed": False,
        "not_in_pending_queue": True,
    }


def get_x_kernel_prompt_package_draft(stage_id: str) -> dict[str, Any]:
    wanted = str(stage_id or "").strip()
    if not wanted:
        return {
            "receipt_type": "x_kernel_prompt_package_draft_lookup",
            "status": "not_found",
            "stage_id": wanted,
            "draft": None,
            "execution_allowed": False,
            "apply_allowed": False,
            "not_in_pending_queue": True,
        }
    for path in _draft_files():
        payload = _load_json(path)
        if payload is not None and str(payload.get("stage_id") or "") == wanted:
            return {
                "receipt_type": "x_kernel_prompt_package_draft_lookup",
                "status": "completed",
                "stage_id": wanted,
                "draft": _normalize(payload, path),
                "execution_allowed": False,
                "apply_allowed": False,
                "not_in_pending_queue": True,
            }
    return {
        "receipt_type": "x_kernel_prompt_package_draft_lookup",
        "status": "not_found",
        "stage_id": wanted,
        "draft": None,
        "execution_allowed": False,
        "apply_allowed": False,
        "not_in_pending_queue": True,
    }
