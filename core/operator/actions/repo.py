from __future__ import annotations

from datetime import UTC, datetime
import subprocess
from pathlib import Path
import re
from typing import Any

from core.brain.commit_proposal_manager import CommitProposalManager
from core.brain.repo_safety_policy import RepoSafetyPolicy
from core.operator.schema import OperatorActionResult, OperatorSafety


GIT_COMMAND_TIMEOUT_SECONDS = 8

LOCAL_ONLY_PATHS = {
    "docker-compose.yml",
    "docker-compose.local.diff",
}

SENSITIVE_FILE_PATTERNS = (
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"(^|/)(?:secret|secrets)(?:/|\.|_|$)"),
    re.compile(r"(^|/)(?:credential|credentials)(?:/|\.|_|$)"),
    re.compile(r"(^|/)(?:key|keys|cert|certs|pem|p12|pfx|jks)(?:/|\.|_|$)"),
)


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    if args == ["status", "--short", "--branch"]:
        from core.operator.actions.status_report import (
            _fast_status,
            _fast_status_enabled,
        )

        if _fast_status_enabled(repo_root):
            return _fast_status(repo_root)
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )
    except subprocess.TimeoutExpired:
        command = "git " + " ".join(args)
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=124,
            stdout="",
            stderr=(
                "limitation: repo status check timed out after "
                f"{GIT_COMMAND_TIMEOUT_SECONDS}s while running {command}"
            ),
        )


def _change_kind(path: str) -> str:
    lowered = path.lower()
    if lowered in LOCAL_ONLY_PATHS:
        return "local_only"
    return "repo"


def _path_from_status_line(line: str) -> str:
    raw_path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in raw_path:
        raw_path = raw_path.rsplit(" -> ", 1)[-1].strip()
    return raw_path.strip('"').replace("\\", "/")


def _parse_branch_header(header: str) -> dict[str, Any]:
    branch = "unknown"
    upstream = None
    cleaned = header.removeprefix("## ").strip()
    left, _, _meta = cleaned.partition("[")
    if "..." in left:
        branch_part, upstream_part = left.split("...", 1)
        branch = branch_part.strip() or "unknown"
        upstream = upstream_part.strip() or None
    elif left:
        branch = left.strip()
    return {
        "branch": branch,
        "upstream": upstream,
    }


def _is_sensitive_commit_target(path_text: str) -> bool:
    lowered = str(path_text or "").lower().replace("\\", "/")
    return any(pattern.search(lowered) for pattern in SENSITIVE_FILE_PATTERNS)


def _is_safe_repo_commit_target(path_text: str) -> bool:
    normalized = str(path_text or "").strip().replace("\\", "/")
    if not normalized:
        return False
    if _change_kind(normalized) == "local_only":
        return False
    if RepoSafetyPolicy.is_blocked_commit_target(normalized):
        return False
    if _is_sensitive_commit_target(normalized):
        return False
    return True


def _collect_repo_candidates(
    status_lines: list[str],
) -> tuple[list[str], list[str], list[str]]:
    candidate_files: list[str] = []
    skipped_files: list[str] = []
    local_only_files: list[str] = []
    for line in status_lines:
        path = _path_from_status_line(line)
        if not path:
            continue
        if _change_kind(path) == "local_only":
            local_only_files.append(path)
            skipped_files.append(path)
            continue
        if _is_safe_repo_commit_target(path):
            candidate_files.append(path)
        else:
            skipped_files.append(path)
    # Preserve order while removing duplicates.
    return (
        list(dict.fromkeys(candidate_files)),
        list(dict.fromkeys(skipped_files)),
        list(dict.fromkeys(local_only_files)),
    )


def _derive_commit_message(
    *,
    candidate_files: list[str],
    commit_message: str,
    summary: str,
) -> str:
    explicit = str(commit_message or "").strip()
    if explicit:
        return explicit
    summary_text = str(summary or "").strip()
    if summary_text:
        normalized = " ".join(summary_text.split())
        return f"chore: {normalized}"
    return CommitProposalManager.proposed_commit_message(candidate_files)


def _extract_commit_sha(commit_stdout: str) -> str:
    # git commit output includes `[branch abc1234]` or `[detached HEAD abc1234]`.
    match = re.search(r"\[.+\s([0-9a-f]{7,40})\]", str(commit_stdout or ""))
    if not match:
        return ""
    return match.group(1)


def _sanitize_git_failure(stderr_text: str, repo_root: Path) -> str:
    message = str(stderr_text or "").strip()
    if "not a git repository" in message.lower():
        return (
            "commit/push unavailable: runtime repo root is not a usable git workspace "
            f"({repo_root})."
        )
    return message or "git status unavailable"


def operator_commit_report(
    *,
    action_id: str,
    repo_root: Path,
    request: dict[str, Any],
) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    mode = str(request.get("mode") or "preview").strip().lower()
    if mode not in {"preview", "apply"}:
        mode = "preview"

    commit_approval = bool(
        (request.get("approval") or {}).get("approved")
        if isinstance(request.get("approval"), dict)
        else request.get("approval", False)
    )
    push_requested = bool(request.get("push", False))
    push_approval = bool(
        (request.get("push_approval") or {}).get("approved")
        if isinstance(request.get("push_approval"), dict)
        else request.get("push_approval", False)
    )
    force_push_requested = bool(request.get("force_push", False))
    selected_files_raw = request.get("selected_files", [])
    selected_files = (
        [str(item).replace("\\", "/") for item in selected_files_raw]
        if isinstance(selected_files_raw, list)
        else []
    )

    status_proc = _run_git(repo_root, ["status", "--short", "--branch"])
    completed = datetime.now(UTC)
    if status_proc.returncode != 0:
        safe_error = _sanitize_git_failure(status_proc.stderr, repo_root)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="git status --short --branch",
            target=str(repo_root),
            stdout_summary=status_proc.stdout[:500],
            stderr_summary=safe_error[:500],
            exit_code=status_proc.returncode,
            data={
                "mode": mode,
                "candidate_files": [],
                "committed_files": [],
                "skipped_files": [],
                "pushed": False,
                "commit_sha": "",
                "commit_created": False,
                "push_performed": False,
                "safety_notes": [
                    "Git status failed; commit/push not attempted.",
                    safe_error,
                ],
                "local_only_files": [],
                "local_only_files_warning": [],
            },
            safety=OperatorSafety(
                allowed=False,
                read_only=False,
                mutates_git=True,
                requires_approval=True,
                denial_reason=safe_error,
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    lines = [line for line in status_proc.stdout.splitlines() if line.strip()]
    branch_meta = _parse_branch_header(lines[0] if lines else "")
    status_lines = lines[1:] if len(lines) > 1 else []
    candidate_files, skipped_files, local_only_files = _collect_repo_candidates(
        status_lines
    )
    commit_message = _derive_commit_message(
        candidate_files=candidate_files,
        commit_message=str(request.get("commit_message") or ""),
        summary=str(request.get("summary") or ""),
    )

    resolved_candidates = candidate_files
    if selected_files:
        missing = [path for path in selected_files if path not in candidate_files]
        if missing:
            completed = datetime.now(UTC)
            return OperatorActionResult(
                action_id=action_id,
                action_name="operator_commit_report",
                mode="operator",
                status="denied",
                started_at=started,
                completed_at=completed,
                command_or_operation="git status --short --branch",
                target=str(repo_root),
                stdout_summary="blocked selection includes non-candidate files",
                stderr_summary="Requested selected_files contain unsafe or unavailable paths.",
                exit_code=0,
                data={
                    "mode": mode,
                    "branch": branch_meta["branch"],
                    "upstream": branch_meta["upstream"],
                    "candidate_files": candidate_files,
                    "committed_files": [],
                    "skipped_files": list(dict.fromkeys(skipped_files + missing)),
                    "selected_files": selected_files,
                    "commit_message": commit_message,
                    "commit_sha": "",
                    "pushed": False,
                    "commit_created": False,
                    "push_performed": False,
                    "safety_notes": [
                        "Selected files must be a subset of safe candidate files.",
                    ],
                    "local_only_files": local_only_files,
                    "local_only_files_warning": local_only_files,
                },
                safety=OperatorSafety(
                    allowed=False,
                    read_only=False,
                    mutates_git=True,
                    requires_approval=False,
                    denial_reason="Unsafe selected files requested.",
                ),
                receipt_label=f"operator_commit_report {action_id}",
            )
        resolved_candidates = selected_files

    preview_notes = [
        "Commit/push is approval-gated.",
        "Protected local-only files are excluded by default.",
        "Push requires separate approval and is never force-pushed.",
    ]

    if mode == "preview":
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="success",
            started_at=started,
            completed_at=completed,
            command_or_operation="preview commit/push candidate set from git status",
            target=str(repo_root),
            stdout_summary=(
                f"candidate_files={len(resolved_candidates)}; skipped_files={len(skipped_files)}; "
                "approval_required=true"
            ),
            stderr_summary="",
            exit_code=0,
            data={
                "mode": "preview",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "approval_required": True,
                "safety_notes": preview_notes,
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=True,
                read_only=True,
                mutates_git=False,
                requires_approval=False,
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    if not commit_approval:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="approval-gated git add/commit",
            target=str(repo_root),
            stdout_summary="commit blocked pending explicit approval",
            stderr_summary="Commit approval is required before mutation.",
            exit_code=0,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "approval_required": True,
                "safety_notes": [
                    "Explicit commit approval is required before commit.",
                ],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=False,
                read_only=False,
                mutates_git=True,
                requires_approval=True,
                denial_reason="Commit approval is required.",
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    if not resolved_candidates:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="approval-gated git add/commit",
            target=str(repo_root),
            stdout_summary="no safe candidate files to commit",
            stderr_summary="No safe repo files are eligible for commit.",
            exit_code=0,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": [],
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "approval_required": False,
                "safety_notes": [
                    "No safe repo files were available for commit.",
                ],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=False,
                read_only=False,
                mutates_git=True,
                requires_approval=False,
                denial_reason="No safe repo files available.",
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    if force_push_requested:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="blocked force push request",
            target=str(repo_root),
            stdout_summary="force push blocked by policy",
            stderr_summary="Force push is not allowed.",
            exit_code=0,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "approval_required": False,
                "safety_notes": ["Force push is blocked by policy."],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=False,
                read_only=False,
                mutates_git=True,
                requires_approval=False,
                denial_reason="Force push is blocked.",
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    if push_requested and not push_approval:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="denied",
            started_at=started,
            completed_at=completed,
            command_or_operation="approval-gated git push",
            target=str(repo_root),
            stdout_summary="push blocked pending explicit approval",
            stderr_summary="Push approval is required before push.",
            exit_code=0,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "approval_required": True,
                "safety_notes": [
                    "Push requires separate explicit approval.",
                ],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=False,
                read_only=False,
                mutates_git=True,
                requires_approval=True,
                denial_reason="Push approval is required.",
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    add_proc = _run_git(repo_root, ["add", "--", *resolved_candidates])
    if add_proc.returncode != 0:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="git add -- <approved-safe-files>",
            target=str(repo_root),
            stdout_summary=add_proc.stdout[:500],
            stderr_summary=add_proc.stderr[:500],
            exit_code=add_proc.returncode,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "safety_notes": ["git add failed; no commit or push occurred."],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=True,
                read_only=False,
                mutates_git=True,
                requires_approval=True,
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    commit_proc = _run_git(
        repo_root,
        ["commit", "-m", commit_message, "--", *resolved_candidates],
    )
    if commit_proc.returncode != 0:
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_commit_report",
            mode="operator",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="git commit -m <message> -- <approved-safe-files>",
            target=str(repo_root),
            stdout_summary=commit_proc.stdout[:500],
            stderr_summary=commit_proc.stderr[:500],
            exit_code=commit_proc.returncode,
            data={
                "mode": "apply",
                "branch": branch_meta["branch"],
                "upstream": branch_meta["upstream"],
                "candidate_files": resolved_candidates,
                "committed_files": [],
                "skipped_files": skipped_files,
                "selected_files": selected_files,
                "commit_message": commit_message,
                "commit_sha": "",
                "pushed": False,
                "commit_created": False,
                "push_performed": False,
                "safety_notes": ["git commit failed; push was not attempted."],
                "local_only_files": local_only_files,
                "local_only_files_warning": local_only_files,
            },
            safety=OperatorSafety(
                allowed=True,
                read_only=False,
                mutates_git=True,
                requires_approval=True,
            ),
            receipt_label=f"operator_commit_report {action_id}",
        )

    commit_sha = _extract_commit_sha(commit_proc.stdout)
    pushed = False
    push_proc: subprocess.CompletedProcess[str] | None = None
    if push_requested:
        push_proc = _run_git(repo_root, ["push", "origin", branch_meta["branch"]])
        if push_proc.returncode != 0:
            completed = datetime.now(UTC)
            return OperatorActionResult(
                action_id=action_id,
                action_name="operator_commit_report",
                mode="operator",
                status="failed",
                started_at=started,
                completed_at=completed,
                command_or_operation="git push origin <branch>",
                target=str(repo_root),
                stdout_summary=push_proc.stdout[:500],
                stderr_summary=push_proc.stderr[:500],
                exit_code=push_proc.returncode,
                data={
                    "mode": "apply",
                    "branch": branch_meta["branch"],
                    "upstream": branch_meta["upstream"],
                    "candidate_files": resolved_candidates,
                    "committed_files": resolved_candidates,
                    "skipped_files": skipped_files,
                    "selected_files": selected_files,
                    "commit_message": commit_message,
                    "commit_sha": commit_sha,
                    "pushed": False,
                    "commit_created": True,
                    "push_performed": False,
                    "safety_notes": [
                        "Commit completed.",
                        "Push failed.",
                    ],
                    "local_only_files": local_only_files,
                    "local_only_files_warning": local_only_files,
                },
                safety=OperatorSafety(
                    allowed=True,
                    read_only=False,
                    mutates_git=True,
                    requires_approval=True,
                ),
                receipt_label=f"operator_commit_report {action_id}",
            )
        pushed = True

    completed = datetime.now(UTC)
    summary = (
        f"committed_files={len(resolved_candidates)}; pushed={str(pushed).lower()}"
    )
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_commit_report",
        mode="operator",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="approval-gated git add/commit/push",
        target=str(repo_root),
        stdout_summary=summary,
        stderr_summary=(
            push_proc.stderr[:500] if push_proc and push_proc.stderr else ""
        ),
        exit_code=0,
        data={
            "mode": "apply",
            "branch": branch_meta["branch"],
            "upstream": branch_meta["upstream"],
            "candidate_files": resolved_candidates,
            "committed_files": resolved_candidates,
            "skipped_files": skipped_files,
            "selected_files": selected_files,
            "commit_message": commit_message,
            "commit_sha": commit_sha,
            "pushed": pushed,
            "commit_created": True,
            "push_performed": pushed,
            "safety_notes": [
                "Commit executed for safe approved repo files only.",
                "Protected local-only files were excluded.",
                "No merge was performed.",
            ],
            "local_only_files": local_only_files,
            "local_only_files_warning": local_only_files,
        },
        safety=OperatorSafety(
            allowed=True,
            read_only=False,
            mutates_git=True,
            requires_approval=True,
        ),
        receipt_label=f"operator_commit_report {action_id}",
    )


def repo_status(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    branch_proc = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_proc = _run_git(repo_root, ["status", "--porcelain"])
    branch_meta_proc = _run_git(repo_root, ["status", "--porcelain", "--branch"])
    upstream_proc = _run_git(
        repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
    )
    completed = datetime.now(UTC)

    combined_stderr = "\n".join(
        chunk.strip()
        for chunk in (
            branch_proc.stderr,
            status_proc.stderr,
            branch_meta_proc.stderr,
            upstream_proc.stderr,
        )
        if chunk.strip()
    )
    combined_stdout = "\n".join(
        chunk.strip()
        for chunk in (
            branch_proc.stdout,
            status_proc.stdout,
            branch_meta_proc.stdout,
            upstream_proc.stdout,
        )
        if chunk.strip()
    )
    ok = (
        branch_proc.returncode == 0
        and status_proc.returncode == 0
        and branch_meta_proc.returncode == 0
    )
    branch = branch_proc.stdout.strip() or "unknown"
    status_lines = [line for line in status_proc.stdout.splitlines() if line.strip()]
    short_status_lines = status_lines[:20]
    clean = ok and len(status_lines) == 0

    upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else None
    branch_header = ""
    meta_lines = [line for line in branch_meta_proc.stdout.splitlines() if line.strip()]
    if meta_lines:
        branch_header = meta_lines[0]

    ahead = 0
    behind = 0
    sync = "unknown"
    sync_limitation: str | None = None
    if upstream is None:
        sync_limitation = "Upstream tracking branch is not configured."
    else:
        if "ahead " in branch_header or "behind " in branch_header:
            import re

            ahead_match = re.search(r"ahead\s+(\d+)", branch_header)
            behind_match = re.search(r"behind\s+(\d+)", branch_header)
            ahead = int(ahead_match.group(1)) if ahead_match else 0
            behind = int(behind_match.group(1)) if behind_match else 0
        if ahead == 0 and behind == 0:
            sync = "in_sync"
        elif ahead > 0 and behind == 0:
            sync = "ahead"
        elif behind > 0 and ahead == 0:
            sync = "behind"
        elif ahead > 0 and behind > 0:
            sync = "diverged"

    return OperatorActionResult(
        action_id=action_id,
        action_name="repo_status",
        status="success" if ok else "failed",
        started_at=started,
        completed_at=completed,
        command_or_operation="git branch --show-current && git status --porcelain",
        target=str(repo_root),
        stdout_summary=(
            f"branch={branch}; clean={clean}; changed_files={len(status_lines)}; sync={sync}"
            if ok
            else combined_stdout[:500]
        ),
        stderr_summary=combined_stderr[:500],
        exit_code=0
        if ok
        else (
            status_proc.returncode
            or branch_proc.returncode
            or branch_meta_proc.returncode
        ),
        data={
            "branch": branch,
            "clean": clean,
            "sync": sync,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "status_lines": short_status_lines,
            "status_line_count": len(status_lines),
            "limitations": [sync_limitation] if sync_limitation else [],
        },
        safety=OperatorSafety(allowed=True),
        receipt_label=f"repo_status {action_id}",
    )


def repo_recent_commits(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    proc = _run_git(repo_root, ["log", "-5", "--oneline"])
    completed = datetime.now(UTC)
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    ok = proc.returncode == 0

    return OperatorActionResult(
        action_id=action_id,
        action_name="repo_recent_commits",
        status="success" if ok else "failed",
        started_at=started,
        completed_at=completed,
        command_or_operation="git log -5 --oneline",
        target=str(repo_root),
        stdout_summary=f"recent_commits={len(lines)}" if ok else proc.stdout[:500],
        stderr_summary=proc.stderr[:500],
        exit_code=proc.returncode,
        data={"commits": lines},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"repo_recent_commits {action_id}",
    )
