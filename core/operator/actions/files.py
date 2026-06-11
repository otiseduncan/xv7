from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.operator.schema import OperatorActionResult, OperatorSafety


def list_project_files(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    files = sorted(
        str(path.relative_to(repo_root)).replace("\\", "/")
        for path in repo_root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    limited = files[:500]
    completed = datetime.now(UTC)

    return OperatorActionResult(
        action_id=action_id,
        action_name="list_project_files",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="filesystem list repo files",
        target=str(repo_root),
        stdout_summary=f"file_count={len(files)}; returned={len(limited)}",
        stderr_summary="",
        exit_code=None,
        data={"files": limited, "truncated": len(files) > len(limited)},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"list_project_files {action_id}",
    )


def read_project_file(*, action_id: str, repo_root: Path, path: str) -> OperatorActionResult:
    started = datetime.now(UTC)
    target = (repo_root / path).resolve()

    if repo_root.resolve() not in (target, *target.parents):
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="read_project_file",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="filesystem read project file",
            target=path,
            stdout_summary="",
            stderr_summary="Denied outside repo root",
            exit_code=None,
            data={},
            safety=OperatorSafety(allowed=False, denial_reason="outside_repo_root"),
            receipt_label=f"read_project_file {action_id}",
        )

    if not target.exists() or not target.is_file():
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="read_project_file",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="filesystem read project file",
            target=str(target),
            stdout_summary="",
            stderr_summary="File not found",
            exit_code=None,
            data={},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"read_project_file {action_id}",
        )

    content = target.read_text(encoding="utf-8", errors="replace")
    snippet = content[:5000]
    completed = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="read_project_file",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="filesystem read project file",
        target=str(target),
        stdout_summary=f"chars={len(content)} returned={len(snippet)}",
        stderr_summary="",
        exit_code=None,
        data={"path": str(target.relative_to(repo_root)).replace("\\", "/"), "content": snippet},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"read_project_file {action_id}",
    )
