from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions import test_runner
from core.operator.actions.test_runner import _validate_single_pytest_target


class FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_test_runner_denies_unknown_preset(tmp_path: Path) -> None:
    result = test_runner(
        action_id="OP-20260611-0501",
        repo_root=tmp_path,
        preset="raw_shell",
    )

    assert result.status == "denied"
    assert result.safety.read_only is True
    assert result.safety.allowed is False
    assert "Unknown test_runner preset" in result.stderr_summary


@pytest.mark.parametrize(
    "target",
    [
        "../tests/test_operator_registry.py",
        "C:/temp/test_operator_registry.py",
        "tests/test_operator_registry.py && whoami",
        "tests/test_operator_registry.py; whoami",
        "core/operator/registry.py",
        "tests/not_python.txt",
    ],
)
def test_single_pytest_denies_unsafe_targets(target: str) -> None:
    denial = _validate_single_pytest_target(target)

    assert denial is not None


def test_single_pytest_allows_safe_test_selector() -> None:
    denial = _validate_single_pytest_target(
        "tests/test_operator_registry.py::test_operator_registry_contains_expected_actions"
    )

    assert denial is None


def test_test_runner_single_pytest_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        calls.append(command)
        return FakeCompletedProcess(0, stdout="1 passed", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = test_runner(
        action_id="OP-20260611-0502",
        repo_root=tmp_path,
        preset="single_pytest",
        test_target="tests/test_operator_registry.py::test_operator_registry_contains_expected_actions",
    )

    assert result.status == "success"
    assert result.data["passed"] is True
    assert result.data["failed_command"] is None
    assert result.data["exit_codes"] == [0]
    assert calls[0][2:5] == ["pytest", "tests/test_operator_registry.py::test_operator_registry_contains_expected_actions", "-v"]


def test_test_runner_stops_on_failed_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        calls.append(command)
        if len(calls) == 1:
            return FakeCompletedProcess(0, stdout="ruff ok", stderr="")
        return FakeCompletedProcess(1, stdout="", stderr="format needed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = test_runner(
        action_id="OP-20260611-0503",
        repo_root=tmp_path,
        preset="lint_backend",
    )

    assert result.status == "failed"
    assert result.data["passed"] is False
    assert "ruff format --check" in result.data["failed_command"]
    assert result.data["exit_codes"] == [0, 1]
    assert len(calls) == 2


def test_test_runner_command_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        raise OSError("missing executable")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = test_runner(
        action_id="OP-20260611-0504",
        repo_root=tmp_path,
        preset="frontend_app",
    )

    assert result.status == "failed"
    assert result.exit_code == 127
    assert result.data["passed"] is False
    assert "Command unavailable" in result.data["stderr_summary"]


def test_test_runner_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1, output="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = test_runner(
        action_id="OP-20260611-0505",
        repo_root=tmp_path,
        preset="single_pytest",
        test_target="tests/test_operator_registry.py",
        timeout_seconds=1,
    )

    assert result.status == "failed"
    assert result.exit_code == 124
    assert "timed out" in result.data["stderr_summary"]
