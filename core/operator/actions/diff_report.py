from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import subprocess
import time
from typing import Any

from core.operator.schema import OperatorActionResult, OperatorSafety, OperatorStatus


MAX_OUTPUT_CHARS = 4000


GitCommand = list[str]


GIT_COMMANDS: dict[str, GitCommand] = {
    "status": ["git", "status", "--short"],
    "name_status": ["git", "diff", "--name-status"],
    "stat": ["git", "diff", "--stat"],
    "shortstat": ["git", "diff", "--shortstat"],
}


def _compact(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    cleaned = text.rstrip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[-max_chars:]


def _display_command(command: GitCommand) -> str:
    return " ".join(command)


def _path_from_status_line(line: str) -> str:
    raw_path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in raw_path:
        return raw_path.rsplit(" -> ", 1)[-1].strip()
    return raw_path.strip('"')


def _changed_files_from_status(status_output: str) -> list[str]:
    files: list[str] = []
    for line in status_output.splitlines():
        path = _path_from_status_line(line)
        if path:
            files.append(path)
    return files


def _risk_flags_for_files(changed_files: list[str]) -> list[str]:
    risks: set[str] = set()
    for file_path in changed_files:
        normalized = file_path.replace("\\", "/")
        lowered = normalized.lower()
        if lowered.startswith("core/"):
            risks.add("backend_runtime")
        if lowered.startswith("tests/"):
            risks.add("test_surface")
        if lowered.startswith("public/"):
            risks.add("frontend_surface")
        if lowered.startswith("docs/"):
            risks.add("docs_only_possible")
        if lowered.startswith(".github/workflows/"):
            risks.add("ci_workflow")
        if lowered in {"dockerfile", "docker-compose.yml", "compose.yml"}:
            risks.add("container_runtime")
        if lowered in {"package.json", "package-lock.json", "pyproject.toml"}:
            risks.add("dependency_or_tooling")
    return sorted(risks)


def _run_git(repo_root: Path, command: GitCommand) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )


def _result(
    *,
    action_id: str,
    repo_root: Path,
    started: datetime,
    status: OperatorStatus,
    stdout_summary: str,
    stderr_summary: str,
    exit_code: int | None,
    data: dict[str, Any],
) -> OperatorActionResult:
    return OperatorActionResult(
        action_id=action_id,
        action_name="diff_report",
        status=status,
        started_at=started,
        completed_at=datetime.now(UTC),
        command_or_operation="read-only git diff summary",
        target=str(repo_root),
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        exit_code=exit_code,
        data=data,
        safety=OperatorSafety(
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=False,
            allowed=True,
        ),
        receipt_label=f"diff_report {action_id}",
    )


def diff_report(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    start_time = time.perf_counter()
    repo_root = repo_root.resolve()
    command_results: dict[str, dict[str, Any]] = {}

    for label, command in GIT_COMMANDS.items():
        display = _display_command(command)
        try:
            completed = _run_git(repo_root, command)
        except OSError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return _result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                status="failed",
                stdout_summary="",
                stderr_summary=f"Git command unavailable: {display}: {exc}",
                exit_code=127,
                data={
                    "failed_command": display,
                    "duration_ms": duration_ms,
                    "command_results": command_results,
                },
            )

        stdout = _compact(completed.stdout)
        stderr = _compact(completed.stderr)
        command_results[label] = {
            "command": display,
            "exit_code": int(completed.returncode),
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
        if int(completed.returncode) != 0:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return _result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                status="failed",
                stdout_summary="",
                stderr_summary=f"Git diff report failed command: {display}",
                exit_code=int(completed.returncode),
                data={
                    "failed_command": display,
                    "duration_ms": duration_ms,
                    "command_results": command_results,
                },
            )

    status_output = command_results["status"]["stdout_tail"]
    changed_files = _changed_files_from_status(status_output)
    risk_flags = _risk_flags_for_files(changed_files)
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    has_changes = bool(changed_files)
    stdout_summary = (
        f"changed_files={len(changed_files)}; "
        f"has_changes={str(has_changes).lower()}; "
        f"risks={','.join(risk_flags) if risk_flags else 'none'}"
    )

    return _result(
        action_id=action_id,
        repo_root=repo_root,
        started=started,
        status="success",
        stdout_summary=stdout_summary,
        stderr_summary="",
        exit_code=0,
        data={
            "has_changes": has_changes,
            "changed_files": changed_files,
            "risk_flags": risk_flags,
            "status_lines": status_output.splitlines(),
            "name_status_lines": command_results["name_status"][
                "stdout_tail"
            ].splitlines(),
            "diff_stat": command_results["stat"]["stdout_tail"],
            "shortstat": command_results["shortstat"]["stdout_tail"],
            "command_results": command_results,
            "duration_ms": duration_ms,
            "next_recommended_action": "run tests before commit"
            if has_changes
            else "none",
        },
    )
