from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from core.operator.actions.diff_report import diff_report

diff_report_module = importlib.import_module("core.operator.actions.diff_report")


class FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_diff_report_clean_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_repo_root: Path, _command: list[str]) -> FakeCompletedProcess:
        return FakeCompletedProcess(0, stdout="", stderr="")

    monkeypatch.setattr(diff_report_module, "_run_git", fake_run)

    result = diff_report(action_id="OP-20260611-0501", repo_root=tmp_path)

    assert result.status == "success"
    assert result.action_name == "diff_report"
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.data["has_changes"] is False
    assert result.data["changed_files"] == []
    assert result.data["risk_flags"] == []
    assert "changed_files=0" in result.stdout_summary


def test_diff_report_summarizes_changed_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    responses = {
        "status": FakeCompletedProcess(
            0,
            stdout=(
                " M core/operator/registry.py\n"
                " M tests/test_operator_registry.py\n"
                "?? docs/example.md\n"
            ),
        ),
        "name_status": FakeCompletedProcess(
            0,
            stdout=(
                "M\tcore/operator/registry.py\n"
                "M\ttests/test_operator_registry.py\n"
                "A\tdocs/example.md\n"
            ),
        ),
        "stat": FakeCompletedProcess(
            0,
            stdout=(
                " core/operator/registry.py | 2 ++\n"
                " tests/test_operator_registry.py | 2 ++\n"
                " docs/example.md | 1 +\n"
                " 3 files changed, 5 insertions(+)\n"
            ),
        ),
        "shortstat": FakeCompletedProcess(
            0,
            stdout="3 files changed, 5 insertions(+)",
        ),
    }

    def fake_run(_repo_root: Path, command: list[str]) -> FakeCompletedProcess:
        for label, expected_command in diff_report_module.GIT_COMMANDS.items():
            if command == expected_command:
                return responses[label]
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(diff_report_module, "_run_git", fake_run)

    result = diff_report(action_id="OP-20260611-0502", repo_root=tmp_path)

    assert result.status == "success"
    assert result.data["has_changes"] is True
    assert result.data["changed_files"] == [
        "core/operator/registry.py",
        "tests/test_operator_registry.py",
        "docs/example.md",
    ]
    assert result.data["risk_flags"] == [
        "backend_runtime",
        "docs_only_possible",
        "test_surface",
    ]
    assert result.data["shortstat"] == "3 files changed, 5 insertions(+)"
    assert result.data["next_recommended_action"] == "run tests before commit"
    assert "changed_files=3" in result.stdout_summary


def test_diff_report_command_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_repo_root: Path, _command: list[str]) -> FakeCompletedProcess:
        raise OSError("git missing")

    monkeypatch.setattr(diff_report_module, "_run_git", fake_run)

    result = diff_report(action_id="OP-20260611-0503", repo_root=tmp_path)

    assert result.status == "failed"
    assert result.exit_code == 127
    assert "Git command unavailable" in result.stderr_summary
    assert result.safety.read_only is True
    assert result.safety.allowed is True


def test_diff_report_git_status_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_repo_root: Path, command: list[str]) -> FakeCompletedProcess:
        if command == diff_report_module.GIT_COMMANDS["status"]:
            return FakeCompletedProcess(128, stderr="fatal: not a git repository")
        return FakeCompletedProcess(0)

    monkeypatch.setattr(diff_report_module, "_run_git", fake_run)

    result = diff_report(action_id="OP-20260611-0504", repo_root=tmp_path)

    assert result.status == "failed"
    assert result.exit_code == 128
    assert "git status --short" in result.stderr_summary
    assert result.data["failed_command"] == "git status --short"
