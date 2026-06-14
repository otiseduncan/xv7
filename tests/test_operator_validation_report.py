from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions import validation_report as validation_report_module
from core.operator.actions.validation_report import operator_validation_report
from core.operator.registry import run_action


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _clean_git(_root: Path, _args: list[str]) -> subprocess.CompletedProcess[str]:
    return _Proc(0, "")  # type: ignore[return-value]


def test_validation_report_python_core_profile_runs_allowed_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")
    observed: list[str] = []

    monkeypatch.setattr(validation_report_module, "_run_git", _clean_git)

    def _fake_run_command(
        _repo_root: Path,
        command: tuple[str, ...],
        _timeout_seconds: int,
    ) -> tuple[int, str, str, int]:
        for display, allowed in validation_report_module.ALLOWED_COMMANDS.items():
            if command == allowed:
                observed.append(display)
                return 0, f"ok: {display}", "", 3
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(validation_report_module, "_run_command", _fake_run_command)

    result = operator_validation_report(
        action_id="OP-VALIDATE-1",
        repo_root=tmp_path,
        profile="python-core",
    )

    assert result.status == "success"
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.data["passed"] is True
    assert observed == validation_report_module.VALIDATION_PROFILES["python-core"]
    assert result.data["selected_commands"] == observed
    assert result.data["first_failure"] is None
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert marker.read_text(encoding="utf-8") == "unchanged\n"


def test_validation_report_auto_adds_compose_for_local_only_compose_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[str] = []

    def _dirty_compose(
        _root: Path, _args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return _Proc(0, " M docker-compose.yml\n?? docker-compose.local.diff\n")  # type: ignore[return-value]

    monkeypatch.setattr(validation_report_module, "_run_git", _dirty_compose)

    def _fake_run_command(
        _repo_root: Path,
        command: tuple[str, ...],
        _timeout_seconds: int,
    ) -> tuple[int, str, str, int]:
        for display, allowed in validation_report_module.ALLOWED_COMMANDS.items():
            if command == allowed:
                observed.append(display)
                return 0, "ok", "", 2
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(validation_report_module, "_run_command", _fake_run_command)

    result = operator_validation_report(
        action_id="OP-VALIDATE-2",
        repo_root=tmp_path,
        profile="frontend",
    )

    assert result.status == "success"
    assert result.data["selected_commands"] == ["npm test", "docker compose config"]
    assert observed == ["npm test", "docker compose config"]
    assert result.data["local_only_files_preserved"] is True
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_validation_report_surfaces_first_failure_and_skips_remaining(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(validation_report_module, "_run_git", _clean_git)

    def _fake_run_command(
        _repo_root: Path,
        command: tuple[str, ...],
        _timeout_seconds: int,
    ) -> tuple[int, str, str, int]:
        for display, allowed in validation_report_module.ALLOWED_COMMANDS.items():
            if command == allowed:
                calls.append(display)
                if display == "python -m ruff check core tests scripts":
                    return 1, "", "F401 unused import", 7
                return 0, "ok", "", 4
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(validation_report_module, "_run_command", _fake_run_command)

    result = operator_validation_report(
        action_id="OP-VALIDATE-3",
        repo_root=tmp_path,
        profile="python-core",
    )

    assert result.status == "failed"
    assert result.data["passed"] is False
    assert (
        result.data["first_failure_command"]
        == "python -m ruff check core tests scripts"
    )
    assert result.data["first_failure"]["stderr_tail"] == "F401 unused import"
    assert calls == [
        "python -m ruff format --check core tests scripts",
        "python -m ruff check core tests scripts",
    ]
    skipped = [
        item for item in result.data["command_results"] if item.get("skipped") is True
    ]
    assert [item["command"] for item in skipped] == [
        "python -m mypy core",
        "python -m pytest",
    ]
    assert "First validation failure" in result.stderr_summary
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_validation_report_blocks_disallowed_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(validation_report_module, "_run_git", _clean_git)

    def _should_not_run(*_args: object, **_kwargs: object) -> tuple[int, str, str, int]:
        raise AssertionError("disallowed commands must not execute")

    monkeypatch.setattr(validation_report_module, "_run_command", _should_not_run)

    result = operator_validation_report(
        action_id="OP-VALIDATE-4",
        repo_root=tmp_path,
        commands=["git push origin main"],
    )

    assert result.status == "denied"
    assert result.safety.allowed is False
    assert "Disallowed validation command" in result.stderr_summary
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_validation_report_is_available_through_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(validation_report_module, "_run_git", _clean_git)
    monkeypatch.setattr(
        validation_report_module,
        "_run_command",
        lambda _root, _command, _timeout: (0, "ok", "", 1),
    )

    result = run_action(
        "operator_validation_report",
        action_id="OP-VALIDATE-5",
        repo_root=tmp_path,
        target="docker-compose",
    )

    assert result.status == "success"
    assert result.action_name == "operator_validation_report"
    assert result.data["selected_commands"] == ["docker compose config"]
