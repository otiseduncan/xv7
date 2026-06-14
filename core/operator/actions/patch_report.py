from __future__ import annotations

from datetime import UTC, datetime
import difflib
import hashlib
from pathlib import Path
from typing import Any

from core.brain.sandbox_writer import SandboxWriteManager
from core.operator.schema import OperatorActionResult, OperatorSafety


MAX_DIFF_LINES_PER_FILE = 80
PROTECTED_LOCAL_ONLY_PATHS = {
    "docker-compose.yml",
    "docker-compose.local.diff",
}
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
}
SENSITIVE_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
)


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_path_text(path_text: str) -> str:
    return path_text.replace("\\", "/").strip().strip('"')


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _relative_to_root(root: Path, candidate: Path) -> str:
    return candidate.resolve().relative_to(root.resolve()).as_posix()


def _is_sensitive_path(relative_path: str) -> bool:
    lowered = relative_path.lower()
    name = Path(lowered).name
    return (
        name in SENSITIVE_NAMES
        or any(name.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)
        or "secret" in lowered
        or "credential" in lowered
        or "/.ssh/" in f"/{lowered}/"
    )


def _is_approved(payload: dict[str, Any]) -> bool:
    approval = payload.get("approval")
    if isinstance(approval, bool):
        return approval
    if not isinstance(approval, dict):
        return False
    return approval.get("approved") is True or approval.get("status") == "approved"


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


def _read_existing(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _sandbox_root(payload: dict[str, Any]) -> Path:
    configured = str(payload.get("sandbox_root") or "").strip()
    if configured:
        return Path(configured).resolve()
    return SandboxWriteManager.sandbox_root()


def _classify_target(
    *,
    repo_root: Path,
    sandbox_root: Path,
    change: dict[str, Any],
) -> dict[str, Any]:
    raw_path = _normalize_path_text(str(change.get("path") or ""))
    requested_scope = str(change.get("scope") or "").lower().strip()
    if not raw_path:
        return {
            "path": raw_path,
            "scope": "blocked",
            "blocked": True,
            "reason": "target file path is required",
        }

    path = Path(raw_path)
    if ".." in path.parts:
        return {
            "path": raw_path,
            "scope": "blocked",
            "blocked": True,
            "reason": "outside-root path traversal is blocked",
        }

    if path.is_absolute():
        resolved = path.resolve()
        if _inside(repo_root, resolved):
            relative_path = _relative_to_root(repo_root, resolved)
            root = repo_root
            scope = "repo"
        elif _inside(sandbox_root, resolved):
            relative_path = _relative_to_root(sandbox_root, resolved)
            root = sandbox_root
            scope = "sandbox"
        else:
            return {
                "path": raw_path,
                "scope": "blocked",
                "blocked": True,
                "reason": "absolute path outside allowed roots is blocked",
            }
    elif requested_scope == "sandbox":
        relative_path = raw_path
        root = sandbox_root
        resolved = (sandbox_root / path).resolve()
        scope = "sandbox"
    else:
        relative_path = raw_path
        root = repo_root
        resolved = (repo_root / path).resolve()
        scope = "repo"

    if not _inside(root, resolved):
        return {
            "path": raw_path,
            "scope": "blocked",
            "blocked": True,
            "reason": f"{scope} target escapes allowed root",
        }

    relative_path = _normalize_path_text(relative_path)
    lowered = relative_path.lower()
    if lowered in PROTECTED_LOCAL_ONLY_PATHS:
        return {
            "path": relative_path,
            "scope": "local_only",
            "blocked": True,
            "reason": f"protected local-only file is blocked by default: {relative_path}",
            "target": resolved,
        }
    if _is_sensitive_path(relative_path):
        return {
            "path": relative_path,
            "scope": "blocked",
            "blocked": True,
            "reason": f"sensitive target is blocked by default: {relative_path}",
            "target": resolved,
        }

    return {
        "path": relative_path,
        "scope": scope,
        "blocked": False,
        "reason": "",
        "target": resolved,
    }


def _result(
    *,
    action_id: str,
    started: datetime,
    repo_root: Path,
    mode: str,
    status: str,
    stdout_summary: str,
    stderr_summary: str,
    data: dict[str, Any],
    allowed: bool,
    read_only: bool,
    mutates_files: bool,
    requires_approval: bool,
) -> OperatorActionResult:
    completed = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_patch_report",
        mode="read_only" if read_only else "operator",
        status=status,  # type: ignore[arg-type]
        started_at=started,
        completed_at=completed,
        command_or_operation=f"operator patch {mode}; no git commit or push",
        target=str(repo_root),
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        exit_code=0 if status == "success" else None,
        data=data,
        safety=OperatorSafety(
            read_only=read_only,
            mutates_files=mutates_files,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=requires_approval,
            allowed=allowed,
            denial_reason=None if allowed else stderr_summary,
        ),
        receipt_label=f"operator_patch_report {action_id}",
    )


def operator_patch_report(
    *,
    action_id: str,
    repo_root: Path,
    request: dict[str, Any],
) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    sandbox_root = _sandbox_root(request)
    mode = str(request.get("mode") or "preview").lower().strip()
    changes = request.get("changes")
    if changes is None and request.get("path"):
        changes = [
            {
                "path": request.get("path"),
                "content": request.get("content", request.get("after", "")),
                "scope": request.get("scope"),
            }
        ]
    if mode not in {"preview", "apply"}:
        mode = "preview"

    base_data: dict[str, Any] = {
        "mode": mode,
        "repo_root": str(repo_root),
        "sandbox_root": str(sandbox_root),
        "commit_created": False,
        "push_performed": False,
        "requires_commit_approval": True,
    }

    if not isinstance(changes, list) or not changes:
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            mode=mode,
            status="denied",
            stdout_summary="",
            stderr_summary="Patch request denied: at least one change is required.",
            data=base_data | {"file_results": [], "changed_files": []},
            allowed=False,
            read_only=mode == "preview",
            mutates_files=mode == "apply",
            requires_approval=mode == "apply",
        )

    file_results: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    repo_targets = 0
    changed_files: list[str] = []
    diff_summary: list[str] = []
    prepared: list[dict[str, Any]] = []

    for change in changes:
        if not isinstance(change, dict):
            blocked.append({"path": "", "reason": "every change must be an object"})
            continue
        classification = _classify_target(
            repo_root=repo_root,
            sandbox_root=sandbox_root,
            change=change,
        )
        after = str(change.get("content", change.get("after", "")))
        result_item: dict[str, Any] = {
            "path": classification["path"],
            "scope": classification["scope"],
            "blocked": classification["blocked"],
            "reason": classification["reason"],
            "changed": False,
            "diff": [],
        }
        if classification["blocked"]:
            blocked.append(
                {
                    "path": str(classification["path"]),
                    "reason": str(classification["reason"]),
                }
            )
            file_results.append(result_item)
            continue

        target = classification["target"]
        before = _read_existing(target)
        changed = before != after
        diff_lines = _diff_for_file(classification["path"], before, after)
        summary = (
            f"Update {classification['path']}: {len(before.splitlines())} -> "
            f"{len(after.splitlines())} lines."
            if changed
            else f"No content change for {classification['path']}."
        )
        if classification["scope"] == "repo":
            repo_targets += 1
        if changed:
            changed_files.append(str(classification["path"]))
        diff_summary.append(summary)
        prepared.append(
            {
                "target": target,
                "after": after,
                "changed": changed,
                "path": classification["path"],
                "scope": classification["scope"],
            }
        )
        file_results.append(
            result_item
            | {
                "changed": changed,
                "before_sha256": _sha256_text(before),
                "after_sha256": _sha256_text(after),
                "diff": diff_lines,
            }
        )

    approval_required = mode == "apply" and repo_targets > 0
    approved = _is_approved(request)
    data = base_data | {
        "target_files": [item["path"] for item in file_results],
        "changed_files": changed_files,
        "diff_summary": diff_summary,
        "file_results": file_results,
        "blocked_targets": blocked,
        "approval_required": approval_required,
        "approval_present": approved,
        "validation_recommended": bool(changed_files),
    }

    if blocked:
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            mode=mode,
            status="denied",
            stdout_summary=f"blocked_targets={len(blocked)}; committed=false; pushed=false",
            stderr_summary=blocked[0]["reason"],
            data=data,
            allowed=False,
            read_only=mode == "preview",
            mutates_files=mode == "apply",
            requires_approval=approval_required,
        )

    if mode == "preview":
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            mode=mode,
            status="success",
            stdout_summary=(
                f"preview_files={len(file_results)}; changed_files={len(changed_files)}; "
                f"approval_required={str(repo_targets > 0).lower()}"
            ),
            stderr_summary="",
            data=data | {"approval_required": repo_targets > 0},
            allowed=True,
            read_only=True,
            mutates_files=False,
            requires_approval=False,
        )

    if approval_required and not approved:
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            mode=mode,
            status="denied",
            stdout_summary="",
            stderr_summary="Patch apply denied: repo mutation approval is required.",
            data=data,
            allowed=False,
            read_only=False,
            mutates_files=True,
            requires_approval=True,
        )

    for item in prepared:
        if not item["changed"]:
            continue
        target = item["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["after"], encoding="utf-8")

    return _result(
        action_id=action_id,
        started=started,
        repo_root=repo_root,
        mode=mode,
        status="success",
        stdout_summary=(
            f"changed_files={len(changed_files)}; committed=false; pushed=false; "
            f"validation_recommended={str(bool(changed_files)).lower()}"
        ),
        stderr_summary="",
        data=data,
        allowed=True,
        read_only=False,
        mutates_files=True,
        requires_approval=approval_required,
    )
