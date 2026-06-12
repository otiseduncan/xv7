from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from core.operator.schema import OperatorActionResult, OperatorSafety


DEFAULT_TIMEOUT_SECONDS = 120
MAX_OUTPUT_CHARS = 4000
UNSAFE_TEST_TARGET_TOKENS = (
    "..",
    ";",
    "&&",
    "||",
    "|",
    ">",
    "<",
    "`",
    "$(",
    "${",
)


Command = list[str]


PRESET_COMMANDS: dict[str, list[Command]] = {
    "unit_backend": [
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--asyncio-mode=auto",
        ]
    ],
    "lint_backend": [
        [sys.executable, "-m", "ruff", "check", "core/", "tests/"],
        [sys.executable, "-m", "ruff", "format", "--check", "core/", "tests/"],
    ],
    "frontend_app": [["npm", "test", "--", "public/app.test.js"]],
    "ci_core": [
        [sys.executable, "-m", "ruff", "check", "core/"],
        [sys.executable, "-m", "ruff", "format", "--check", "core/"],
        [sys.executable, "-m", "mypy", "core/", "--ignore-missing-imports"],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--asyncio-mode=auto",
        ],
    ],
    "ci_full_safe": [
        [sys.executable, "-m", "ruff", "check", "core/", "tests/"],
        [sys.executable, "-m", "ruff", "format", "--check", "core/", "tests/"],
        [sys.executable, "-m", "mypy", "core/", "--ignore-missing-imports"],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--asyncio-mode=auto",
        ],
        ["npm", "test", "--", "public/app.test.js"],
    ],
}


DISPLAY_COMMANDS: dict[str, list[str]] = {
    preset: [_display_command(command) for command in commands]
    for preset, commands in PRESET_COMMANDS.items()
}


def _display_command(command: Command) -> str:
    display_parts = ["python" if part == sys.executable else part for part in command]
    return " ".join(display_parts)


def _compact(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[-max_chars:]


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
        action_name="test_runner",
        status="denied",
        started_at=started,
        completed_at=completed,
        command_or_operation="test runner denied before command execution",
        target=str(repo_root),
        stdout_summary="",
        stderr_summary=reason,
        exit_code=None,
        data=data or {},
        safety=OperatorSafety(
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=False,
            allowed=False,
            denial_reason=reason,
        ),
        receipt_label=f"test_runner {action_id}",
    )


def _validate_single_pytest_target(test_target: str) -> str | None:
    if not test_target or not test_target.strip():
        return "single_pytest requires a test target."
    if any(token in test_target for token in UNSAFE_TEST_TARGET_TOKENS):
        return f"Unsafe single_pytest target is denied: {test_target}"
    if re.match(r"^[A-Za-z]:", test_target):
        return f"Absolute single_pytest target is denied: {test_target}"
    path_part = test_target.split("::", 1)[0]
    path = Path(path_part)
    if path.is_absolute():
        return f"Absolute single_pytest target is denied: {test_target}"
    if not path_part.startswith("tests/") and not path_part.startswith("tests\\"):
        return f"single_pytest target must be under tests/: {test_target}"
    if not path_part.endswith(".py"):
        return f"single_pytest target must point to a Python test file: {test_target}"
    return None


def _commands_for_preset(preset: str, test_target: str | None) -> list[Command] | None:
    if preset == "single_pytest":
        target = test_target or ""
        return [
            [
                sys.executable,
                "-m",
                "pytest",
                target,
                "-v",
                "--tb=short",
                "--asyncio-mode=auto",
            ]
        ]
    return PRESET_COMMANDS.get(preset)


def _display_commands_for_preset(preset: str, test_target: str | None) -> list[str]:
    if preset == "single_pytest":
        target = test_target or ""
        return [
            "python -m pytest "
            f"{target} -v --tb=short --asyncio-mode=auto"
        ]
    return DISPLAY_COMMANDS.get(preset, [])


def _normalize_preset(preset: str | None) -> str:
    return (preset or "ci_core").strip()


def test_runner(
    *,
    action_id: str,
    repo_root: Path,
    preset: str = "ci_core",
    test_target: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> OperatorActionResult:
    started = datetime.now(UTC)
    start_time = time.perf_counter()
    repo_root = repo_root.resolve()
    selected_preset = _normalize_preset(preset)

    if selected_preset == "single_pytest":
        denial = _validate_single_pytest_target(test_target or "")
        if denial:
            return _denied_result(
                action_id=action_id,
                repo_root=repo_root,
                started=started,
                reason=denial,
                data={"preset": selected_preset, "test_target": test_target},
            )
    elif selected_preset not in PRESET_COMMANDS:
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason=f"Unknown test_runner preset denied: {selected_preset}",
            data={
                "preset": selected_preset,
                "allowed_presets": sorted([*PRESET_COMMANDS.keys(), "single_pytest"]),
            },
        )

    commands = _commands_for_preset(selected_preset, test_target)
    if commands is None:
        return _denied_result(
            action_id=action_id,
            repo_root=repo_root,
            started=started,
            reason=f"No commands mapped for preset: {selected_preset}",
            data={"preset": selected_preset},
        )

    command_results: list[dict[str, Any]] = []
    exit_codes: list[int] = []
    failed_command: str | None = None
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for command in commands:
        display = _display_command(command)
        try:
            completed_process = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            exit_code = int(completed_process.returncode)
            stdout = _compact(completed_process.stdout)
            stderr = _compact(completed_process.stderr)
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = _compact(exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = f"Command timed out after {timeout_seconds}s: {display}"
        except OSError as exc:
            exit_code = 127
            stdout = ""
            stderr = f"Command unavailable: {display}: {exc}"

        exit_codes.append(exit_code)
        command_results.append(
            {
                "command": display,
                "exit_code": exit_code,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
        )
        if stdout:
            stdout_parts.append(f"$ {display}\n{stdout}")
        if stderr:
            stderr_parts.append(f"$ {display}\n{stderr}")
        if exit_code != 0:
            failed_command = display
            break

    passed = failed_command is None
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    completed = datetime.now(UTC)
    stdout_summary = (
        f"preset={selected_preset}; passed={str(passed).lower()}; "
        f"commands_run={len(exit_codes)}; duration_ms={duration_ms}"
    )
    stderr_summary = "" if passed else f"Test runner failed command: {failed_command}"

    return OperatorActionResult(
        action_id=action_id,
        action_name="test_runner",
        status="success" if passed else "failed",
        started_at=started,
        completed_at=completed,
        command_or_operation="allowlisted test runner preset execution",
        target=str(repo_root),
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        exit_code=0 if passed else exit_codes[-1],
        data={
            "preset": selected_preset,
            "test_target": test_target,
            "commands": _display_commands_for_preset(selected_preset, test_target),
            "passed": passed,
            "failed_command": failed_command,
            "exit_codes": exit_codes,
            "command_results": command_results,
            "stdout_summary": _compact("\n\n".join(stdout_parts)),
            "stderr_summary": _compact("\n\n".join(stderr_parts)),
            "duration_ms": duration_ms,
        },
        safety=OperatorSafety(allowed=True),
        receipt_label=f"test_runner {action_id}",
    )
