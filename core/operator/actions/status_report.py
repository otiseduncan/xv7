from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from core.operator.schema import OperatorActionResult, OperatorSafety


GIT_TIMEOUT_SECONDS = 8
LOCAL_ONLY_PATHS = {
    "docker-compose.yml",
    "docker-compose.local.diff",
}
SANDBOX_PATH_PREFIXES = (
    "generated-sites/",
    "xoduz-sandbox/",
)
BASE_VALIDATION_COMMANDS = [
    "python -m ruff format --check core tests scripts",
    "python -m ruff check core tests scripts",
    "python -m mypy core",
    "python -m pytest",
]
FAST_STATUS_PATHSPEC = ["--", ".", ":!node_modules"]


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=124,
            stdout="",
            stderr=f"limitation: git check timed out after {GIT_TIMEOUT_SECONDS}s",
        )


def _fast_status_enabled(repo_root: Path) -> bool:
    enabled = os.getenv("XV7_OPERATOR_FAST_GIT_STATUS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return False
    configured_root = os.getenv("XV7_OPERATOR_REPO_ROOT", "").strip()
    if not configured_root:
        return True
    return repo_root.resolve() == Path(configured_root).expanduser().resolve()


def _status_line_from_name_status(line: str, *, staged: bool) -> str:
    parts = line.split("\t")
    if not parts:
        return ""
    status = parts[0][:1]
    path = parts[-1].strip().replace("\\", "/")
    if not path:
        return ""
    code = f"{status} " if staged else f" {status}"
    return f"{code} {path}"


def _fast_status(repo_root: Path) -> subprocess.CompletedProcess[str]:
    branch_proc = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch_proc.returncode != 0:
        return branch_proc

    branch = branch_proc.stdout.strip() or "unknown"
    upstream_proc = _run_git(
        repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
    )
    upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else ""
    header = f"## {branch}"
    if upstream:
        header = f"{header}...{upstream}"
        counts_proc = _run_git(
            repo_root, ["rev-list", "--left-right", "--count", "HEAD...@{u}"]
        )
        if counts_proc.returncode == 0:
            counts = counts_proc.stdout.split()
            if len(counts) == 2:
                ahead, behind = counts
                meta = []
                if ahead != "0":
                    meta.append(f"ahead {ahead}")
                if behind != "0":
                    meta.append(f"behind {behind}")
                if meta:
                    header = f"{header} [{', '.join(meta)}]"

    lines = [header]
    for args, staged in (
        (["diff", "--name-status", *FAST_STATUS_PATHSPEC], False),
        (["diff", "--cached", "--name-status", *FAST_STATUS_PATHSPEC], True),
    ):
        proc = _run_git(repo_root, args)
        if proc.returncode != 0:
            return proc
        for line in proc.stdout.splitlines():
            status_line = _status_line_from_name_status(line, staged=staged)
            if status_line:
                lines.append(status_line)

    untracked_proc = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"])
    if untracked_proc.returncode != 0:
        return untracked_proc
    lines.extend(
        "?? " + line.strip().replace("\\", "/")
        for line in untracked_proc.stdout.splitlines()
        if line.strip()
    )
    return subprocess.CompletedProcess(
        args=["git", "fast-status"],
        returncode=0,
        stdout="\n".join(lines) + "\n",
        stderr="",
    )


def _read_status(repo_root: Path) -> subprocess.CompletedProcess[str]:
    if _fast_status_enabled(repo_root):
        return _fast_status(repo_root)
    return _run_git(repo_root, ["status", "--short", "--branch"])


def _parse_branch_header(header: str) -> dict[str, Any]:
    branch = "unknown"
    upstream = None
    ahead = 0
    behind = 0
    sync = "unknown"
    cleaned = header.removeprefix("## ").strip()
    left, _, meta = cleaned.partition("[")
    if "..." in left:
        branch_part, upstream_part = left.split("...", 1)
        branch = branch_part.strip() or "unknown"
        upstream = upstream_part.strip() or None
    elif left:
        branch = left.strip()

    meta_text = meta.rstrip("]")
    ahead_match = re.search(r"ahead\s+(\d+)", meta_text)
    behind_match = re.search(r"behind\s+(\d+)", meta_text)
    ahead = int(ahead_match.group(1)) if ahead_match else 0
    behind = int(behind_match.group(1)) if behind_match else 0
    if ahead == 0 and behind == 0 and upstream:
        sync = "in_sync"
    elif ahead > 0 and behind == 0:
        sync = "ahead"
    elif behind > 0 and ahead == 0:
        sync = "behind"
    elif ahead > 0 and behind > 0:
        sync = "diverged"
    return {
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "sync": sync,
    }


def _path_from_status_line(line: str) -> str:
    raw_path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in raw_path:
        raw_path = raw_path.rsplit(" -> ", 1)[-1].strip()
    return raw_path.strip('"').replace("\\", "/")


def _change_kind(path: str) -> str:
    lowered = path.lower()
    if lowered in LOCAL_ONLY_PATHS:
        return "local_only"
    if any(lowered.startswith(prefix) for prefix in SANDBOX_PATH_PREFIXES):
        return "sandbox"
    return "repo"


def _changed_files(status_lines: list[str]) -> list[dict[str, str]]:
    changed: list[dict[str, str]] = []
    for line in status_lines:
        path = _path_from_status_line(line)
        if not path:
            continue
        changed.append(
            {
                "status": line[:2].strip() or "unknown",
                "path": path,
                "scope": _change_kind(path),
            }
        )
    return changed


def _validation_commands(changed_files: list[dict[str, str]]) -> list[str]:
    commands = list(BASE_VALIDATION_COMMANDS)
    paths = [item["path"].lower() for item in changed_files]
    if any(
        path.startswith("public/") or path in {"package.json", "package-lock.json"}
        for path in paths
    ):
        commands.append("npm test")
    if any(
        path in {"docker-compose.yml", "compose.yml"} or path.startswith("docker/")
        for path in paths
    ):
        commands.append("docker compose config")
    return commands


def _sanitize_git_failure(stderr_text: str, repo_root: Path) -> str:
    message = str(stderr_text or "").strip()
    if "not a git repository" in message.lower():
        return (
            "repo status unavailable: runtime repo root is not a usable git workspace "
            f"({repo_root})."
        )
    return message or "git status unavailable"


def operator_status_report(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    proc = _read_status(repo_root)
    completed = datetime.now(UTC)

    if proc.returncode != 0:
        safe_error = _sanitize_git_failure(proc.stderr, repo_root)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_status_report",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="read-only git status --short --branch",
            target=str(repo_root),
            stdout_summary=proc.stdout[:500],
            stderr_summary=safe_error[:500],
            exit_code=proc.returncode,
            data={"repo_root": str(repo_root), "limitations": [safe_error]},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"operator_status_report {action_id}",
        )

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    branch_meta = _parse_branch_header(lines[0] if lines else "")
    changed = _changed_files(lines[1:])
    repo_files = [item["path"] for item in changed if item["scope"] == "repo"]
    local_only_files = [
        item["path"] for item in changed if item["scope"] == "local_only"
    ]
    sandbox_files = [item["path"] for item in changed if item["scope"] == "sandbox"]
    validation_commands = _validation_commands(changed)
    clean = not changed

    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_status_report",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="read-only git status --short --branch",
        target=str(repo_root),
        stdout_summary=(
            f"branch={branch_meta['branch']}; clean={str(clean).lower()}; "
            f"changed_files={len(changed)}; sync={branch_meta['sync']}; "
            f"local_only={len(local_only_files)}"
        ),
        stderr_summary="",
        exit_code=0,
        data={
            "repo_root": str(repo_root),
            "branch": branch_meta["branch"],
            "upstream": branch_meta["upstream"],
            "ahead": branch_meta["ahead"],
            "behind": branch_meta["behind"],
            "sync": branch_meta["sync"],
            "clean": clean,
            "changed_files": changed,
            "repo_files": repo_files,
            "local_only_files": local_only_files,
            "sandbox_files": sandbox_files,
            "protected_local_only_files": local_only_files,
            "validation_commands": validation_commands,
            "docker_compose_config_recommended": "docker compose config"
            in validation_commands,
            "repo_write_policy": "operator approval required before repo writes",
            "sandbox_write_policy": "sandbox writes must remain under configured sandbox root",
            "commit_push_waiting_for_approval": bool(repo_files or local_only_files),
            "commit_created": False,
            "push_performed": False,
        },
        safety=OperatorSafety(
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=False,
            allowed=True,
        ),
        receipt_label=f"operator_status_report {action_id}",
    )
