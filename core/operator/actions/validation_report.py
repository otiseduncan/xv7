from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from core.operator.schema import OperatorActionResult, OperatorSafety


DEFAULT_TIMEOUT_SECONDS = 300
MAX_OUTPUT_CHARS = 4000
Command = tuple[str, ...]


ALLOWED_COMMANDS: dict[str, Command] = {
    "python -m ruff format --check core tests scripts": (
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        "core",
        "tests",
        "scripts",
    ),
    "python -m ruff check core tests scripts": (
        sys.executable,
        "-m",
        "ruff",
        "check",
        "core",
        "tests",
        "scripts",
    ),
    "python -m mypy core": (sys.executable, "-m", "mypy", "core"),
    "python -m pytest": (sys.executable, "-m", "pytest"),
    "npm test": ("npm", "test"),
    "docker compose config": ("docker", "compose", "config"),
}

VALIDATION_PROFILES: dict[str, list[str]] = {
    "python-core": [
        "python -m ruff format --check core tests scripts",
        "python -m ruff check core tests scripts",
        "python -m mypy core",
        "python -m pytest",
    ],
    "frontend": ["npm test"],
    "docker-compose": ["docker compose config"],
    "all-safe": [
        "python -m ruff format --check core tests scripts",
        "python -m ruff check core tests scripts",
        "python -m mypy core",
        "python -m pytest",
        "npm test",
        "docker compose config",
    ],
}


def _compact(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[-max_chars:]


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr=f"git status unavailable: {exc}",
        )


def _run_command(
    repo_root: Path, command: Command, timeout_seconds: int
) -> tuple[int, str, str, int]:
    started = time.perf_counter()
    env = os.environ.copy()
    for isolated_name in (
        "CORE_API_KEY",
        "XV7_API_KEY",
        "WEBUI_SECRET_KEY",
        "XV7_BRAIN_RECORDS_PATH",
    ):
        env.pop(isolated_name, None)
    env["XV7_BRAIN_RUNTIME_RECORDS_PATH"] = "/tmp/xv7-brain-runtime-records"
    env.setdefault("RUFF_CACHE_DIR", "/tmp/xv7-ruff-cache")
    env.setdefault("MYPY_CACHE_DIR", "/tmp/xv7-mypy-cache")
    pytest_addopts = str(env.get("PYTEST_ADDOPTS", "")).strip()
    if "-p no:cacheprovider" not in pytest_addopts:
        env["PYTEST_ADDOPTS"] = (
            f"{pytest_addopts} -p no:cacheprovider"
            if pytest_addopts
            else "-p no:cacheprovider"
        )
    try:
        proc = subprocess.run(
            list(command),
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return (
            int(proc.returncode),
            _compact(proc.stdout),
            _compact(proc.stderr),
            duration_ms,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = _compact(exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return 124, stdout, f"Command timed out after {timeout_seconds}s", duration_ms
    except OSError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return 127, "", f"Command unavailable: {exc}", duration_ms


def _docker_compose_modified(repo_root: Path) -> bool:
    tracked_proc = _run_git(
        repo_root,
        ["diff", "--name-only", "--", "docker-compose.yml", "compose.yml", "docker"],
    )
    staged_proc = _run_git(
        repo_root,
        [
            "diff",
            "--cached",
            "--name-only",
            "--",
            "docker-compose.yml",
            "compose.yml",
            "docker",
        ],
    )
    untracked_proc = _run_git(
        repo_root,
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "docker-compose.yml",
            "compose.yml",
            "docker",
        ],
    )
    outputs = [
        proc.stdout
        for proc in (tracked_proc, staged_proc, untracked_proc)
        if proc.returncode == 0
    ]
    for line in "\n".join(outputs).splitlines():
        path = line.strip().replace("\\", "/")
        if path in {"docker-compose.yml", "compose.yml"} or path.startswith("docker/"):
            return True
    return False


def _commands_for_request(
    *,
    profile: str,
    commands: list[str] | None,
    include_docker_if_modified: bool,
    repo_root: Path,
) -> tuple[list[str], str | None]:
    if commands:
        unknown = [command for command in commands if command not in ALLOWED_COMMANDS]
        if unknown:
            return [], f"Disallowed validation command: {unknown[0]}"
        selected = list(dict.fromkeys(commands))
    else:
        selected = list(VALIDATION_PROFILES.get(profile, []))
        if not selected:
            return [], f"Unknown validation profile: {profile}"

    if (
        include_docker_if_modified
        and "docker compose config" not in selected
        and _docker_compose_modified(repo_root)
    ):
        selected.append("docker compose config")
    return selected, None


def _denied_result(
    *,
    action_id: str,
    repo_root: Path,
    started: datetime,
    reason: str,
    profile: str,
    commands: list[str] | None,
) -> OperatorActionResult:
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_validation_report",
        status="denied",
        started_at=started,
        completed_at=datetime.now(UTC),
        command_or_operation="allowlisted validation report denied before execution",
        target=str(repo_root),
        stdout_summary="",
        stderr_summary=reason,
        exit_code=None,
        data={
            "profile": profile,
            "requested_commands": commands or [],
            "allowed_profiles": sorted(VALIDATION_PROFILES),
            "allowed_commands": sorted(ALLOWED_COMMANDS),
            "passed": False,
            "first_failure": reason,
            "commit_created": False,
            "push_performed": False,
        },
        safety=OperatorSafety(
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=False,
            allowed=False,
            denial_reason=reason,
        ),
        receipt_label=f"operator_validation_report {action_id}",
    )


def operator_validation_report(
    *,
    action_id: str,
    repo_root: Path,
    profile: str = "python-core",
    commands: list[str] | None = None,
    include_docker_if_modified: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> OperatorActionResult:
    started = datetime.now(UTC)
    start_time = time.perf_counter()
    repo_root = repo_root.resolve()
    selected_profile = (profile or "python-core").strip()
    selected_commands, denial = _commands_for_request(
        profile=selected_profile,
        commands=commands,
        include_docker_if_modified=include_docker_if_modified,
        repo_root=repo_root,
    )
    if denial:
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason=denial,
            profile=selected_profile,
            commands=commands,
        )

    command_results: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None
    for display in selected_commands:
        exit_code, stdout, stderr, duration_ms = _run_command(
            repo_root,
            ALLOWED_COMMANDS[display],
            timeout_seconds,
        )
        result = {
            "command": display,
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "duration_ms": duration_ms,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
            "skipped": False,
        }
        command_results.append(result)
        if exit_code != 0:
            first_failure = result
            break

    if first_failure is not None:
        for display in selected_commands[len(command_results) :]:
            command_results.append(
                {
                    "command": display,
                    "exit_code": None,
                    "passed": False,
                    "duration_ms": 0,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "skipped": True,
                    "skip_reason": "not run after first validation failure",
                }
            )

    passed = first_failure is None
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    first_failure_command = (
        str(first_failure.get("command")) if first_failure is not None else None
    )
    exit_code = 0
    if first_failure is not None:
        exit_code = int(first_failure.get("exit_code") or 1)
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_validation_report",
        status="success" if passed else "failed",
        started_at=started,
        completed_at=datetime.now(UTC),
        command_or_operation="allowlisted validation report execution",
        target=str(repo_root),
        stdout_summary=(
            f"profile={selected_profile}; passed={str(passed).lower()}; "
            f"commands_selected={len(selected_commands)}; "
            f"commands_run={len([item for item in command_results if not item.get('skipped')])}; "
            f"duration_ms={duration_ms}"
        ),
        stderr_summary=""
        if passed
        else f"First validation failure: {first_failure_command}",
        exit_code=exit_code,
        data={
            "profile": selected_profile,
            "selected_commands": selected_commands,
            "command_results": command_results,
            "passed": passed,
            "first_failure": first_failure,
            "first_failure_command": first_failure_command,
            "duration_ms": duration_ms,
            "commit_created": False,
            "push_performed": False,
            "local_only_files_preserved": True,
        },
        safety=OperatorSafety(
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=False,
            allowed=True,
        ),
        receipt_label=f"operator_validation_report {action_id}",
    )
