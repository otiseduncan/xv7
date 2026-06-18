from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from receipts import RECEIPTS_DIR, WORKSPACE_DIR, locked_flags, utc_iso, write_json
from safety import safe_workspace_path


def create_workspace_draft(path: str, content: str, stage_id: str | None, plan: dict[str, Any] | None) -> dict[str, Any]:
    try:
        target = safe_workspace_path(path)
    except ValueError as exc:
        return {"status": "rejected", "error": str(exc), "workspace_path": str(WORKSPACE_DIR), **locked_flags()}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    receipt = {
        "receipt_type": "x_native_workspace_draft",
        "created_at": utc_iso(),
        "workspace_file": str(target),
        "relative_path": str(target.relative_to(WORKSPACE_DIR.resolve())),
        "stage_id": stage_id,
        "plan": plan,
        **locked_flags(),
    }
    paths = write_json(RECEIPTS_DIR, "workspace_draft", receipt, "latest_workspace_draft_receipt.json")
    return {
        "status": "draft_created",
        "workspace_file": str(target),
        "workspace_path": str(WORKSPACE_DIR),
        "receipt_path": paths["path"],
        "latest_receipt_path": paths.get("latest_path"),
        **locked_flags(),
    }


def list_workspace() -> dict[str, Any]:
    files = []
    for path in sorted(WORKSPACE_DIR.rglob("*")):
        if path.is_file():
            files.append({
                "path": str(path),
                "relative_path": str(path.relative_to(WORKSPACE_DIR)),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            })
    return {"status": "completed", "workspace_path": str(WORKSPACE_DIR), "files": files, **locked_flags()}
