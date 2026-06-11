from __future__ import annotations

from datetime import UTC, datetime
import subprocess
from pathlib import Path

from core.operator.schema import OperatorActionResult, OperatorSafety


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )


def repo_status(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    branch_proc = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_proc = _run_git(repo_root, ["status", "--porcelain"])
    branch_meta_proc = _run_git(repo_root, ["status", "--porcelain", "--branch"])
    upstream_proc = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    completed = datetime.now(UTC)

    combined_stderr = "\n".join(
        chunk.strip()
        for chunk in (branch_proc.stderr, status_proc.stderr, branch_meta_proc.stderr, upstream_proc.stderr)
        if chunk.strip()
    )
    combined_stdout = "\n".join(
        chunk.strip()
        for chunk in (branch_proc.stdout, status_proc.stdout, branch_meta_proc.stdout, upstream_proc.stdout)
        if chunk.strip()
    )
    ok = branch_proc.returncode == 0 and status_proc.returncode == 0 and branch_meta_proc.returncode == 0
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
        exit_code=0 if ok else (status_proc.returncode or branch_proc.returncode or branch_meta_proc.returncode),
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
