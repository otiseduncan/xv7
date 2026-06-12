from __future__ import annotations

from datetime import UTC, datetime
import difflib
import hashlib
import os
from pathlib import Path
from typing import Any

from core.operator.schema import OperatorActionResult, OperatorSafety


MAX_DIFF_LINES_PER_FILE = 80


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_patch(patch: dict[str, Any]) -> dict[str, Any]:
    changes = patch.get("changes")
    if changes is None and patch.get("path"):
        changes = [
            {
                "path": patch.get("path"),
                "content": patch.get("content", patch.get("after", "")),
            }
        ]
    normalized = dict(patch)
    normalized["changes"] = changes or []
    return normalized


def _approved(patch: dict[str, Any], approval: dict[str, Any] | None) -> bool:
    approval_info = approval if approval is not None else patch.get("approval")
    if not isinstance(approval_info, dict):
        return False
    return (
        approval_info.get("approved") is True
        or approval_info.get("status") == "approved"
    )


def _inside_repo(repo_root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _safe_target_path(repo_root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    if not raw_path or not raw_path.strip():
        return None, "Patch change path is required."
    path = Path(raw_path)
    if path.is_absolute():
        return None, f"Absolute patch paths are denied: {raw_path}"
    if any(part == ".." for part in path.parts):
        return None, f"outside-root path traversal is denied: {raw_path}"
    if path.parts and path.parts[0] == ".git":
        return None, f"Git internals cannot be patched by operator action: {raw_path}"
    target = (repo_root / path).resolve()
    if not _inside_repo(repo_root, target):
        return None, f"Patch path resolves outside repo root: {raw_path}"
    return target, None


def _read_existing(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _diff_for_file(relative_path: str, before: str, after: str) -> list[str]:
    diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )
    return diff[:MAX_DIFF_LINES_PER_FILE]


def _denied_result(
    *,
    action_id: str,
    repo_root: Path,
    started: datetime,
    reason: str,
    data: dict[str, Any] | None = None,
) -> OperatorActionResult:
    completed = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="apply_approved_patch",
        mode="operator",
        status="denied",
        started_at=started,
        completed_at=completed,
        command_or_operation="approval-gated patch apply denied before mutation",
        target=str(repo_root),
        stdout_summary="",
        stderr_summary=reason,
        exit_code=None,
        data=data or {},
        safety=OperatorSafety(
            read_only=False,
            mutates_files=True,
            requires_approval=True,
            allowed=False,
            denial_reason=reason,
        ),
        receipt_label=f"apply_approved_patch {action_id}",
    )


def apply_approved_patch(
    *,
    action_id: str,
    repo_root: Path,
    patch: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    normalized = _normalize_patch(patch)
    source_plan_id = str(normalized.get("source_plan_id", ""))
    risk = str(normalized.get("risk", "unknown"))
    changes = normalized.get("changes", [])

    if not repo_root.exists() or not repo_root.is_dir():
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason="Repo root does not exist or is not a directory.",
            data={"repo_root": str(repo_root)},
        )

    if not _approved(normalized, approval):
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason="Patch apply denied: explicit approval is required before mutation.",
            data={"source_plan_id": source_plan_id, "risk": risk},
        )

    if not isinstance(changes, list) or not changes:
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason="Patch apply denied: at least one change is required.",
            data={"source_plan_id": source_plan_id, "risk": risk},
        )

    prepared: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict):
            return _denied_result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                reason="Patch apply denied: every change must be an object.",
            )
        raw_path = str(change.get("path", ""))
        target_path, denial = _safe_target_path(repo_root, raw_path)
        if denial or target_path is None:
            return _denied_result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                reason=f"Patch apply denied: {denial}",
                data={"denied_path": raw_path, "source_plan_id": source_plan_id},
            )
        if "content" not in change and "after" not in change:
            return _denied_result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                reason=f"Patch apply denied: content is required for {raw_path}.",
                data={"denied_path": raw_path, "source_plan_id": source_plan_id},
            )
        after = str(change.get("content", change.get("after", "")))
        prepared.append({"path": raw_path, "target": target_path, "after": after})

    changed_files: list[str] = []
    file_results: list[dict[str, Any]] = []
    diff_summary: list[str] = []

    for item in prepared:
        target_path = item["target"]
        relative_path = item["path"]
        before = _read_existing(target_path)
        after = item["after"]
        if before == after:
            diff_lines: list[str] = []
            summary = f"No content change for {relative_path}."
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(after, encoding="utf-8")
            changed_files.append(relative_path)
            diff_lines = _diff_for_file(relative_path, before, after)
            summary = (
                f"Updated {relative_path}: {len(before.splitlines())} -> "
                f"{len(after.splitlines())} lines."
            )
        diff_summary.append(summary)
        file_results.append(
            {
                "path": relative_path,
                "before_sha256": _sha256_text(before),
                "after_sha256": _sha256_text(after),
                "changed": before != after,
                "diff": diff_lines,
            }
        )

    completed = datetime.now(UTC)
    tests = list(normalized.get("test_commands", []))
    return OperatorActionResult(
        action_id=action_id,
        action_name="apply_approved_patch",
        mode="operator",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="approval-gated file patch apply; no git commit or push",
        target=str(repo_root),
        stdout_summary=(
            f"changed_files={len(changed_files)}; committed=false; "
            f"requires_commit_approval=true"
        ),
        stderr_summary="",
        exit_code=0,
        data={
            "source_plan_id": source_plan_id,
            "risk": risk,
            "changed_files": changed_files,
            "diff_summary": diff_summary,
            "file_results": file_results,
            "tests_recommended": tests,
            "committed": False,
            "requires_commit_approval": True,
            "cwd_unchanged": str(Path.cwd()) == os.getcwd(),
        },
        safety=OperatorSafety(
            read_only=False,
            mutates_files=True,
            requires_approval=True,
            allowed=True,
        ),
        receipt_label=f"apply_approved_patch {action_id}",
    )
