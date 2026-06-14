from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions import status_report as status_report_module
from core.operator.actions.status_report import operator_status_report
from core.operator.registry import run_action


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_operator_status_report_clean_workspace_is_read_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args == ["status", "--short", "--branch"]
        return _Proc(0, "## main...origin/main\n")  # type: ignore[return-value]

    monkeypatch.setattr(status_report_module, "_run_git", _fake_run_git)

    result = operator_status_report(action_id="OP-STATUS-1", repo_root=tmp_path)

    assert result.status == "success"
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.data["branch"] == "main"
    assert result.data["sync"] == "in_sync"
    assert result.data["clean"] is True
    assert result.data["changed_files"] == []
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert marker.read_text(encoding="utf-8") == "unchanged\n"


def test_operator_status_report_classifies_local_only_and_recommends_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args == ["status", "--short", "--branch"]
        return _Proc(
            0,
            (
                "## code22/split-answer-contract...origin/code22/split-answer-contract [ahead 2]\n"
                " M docker-compose.yml\n"
                "?? docker-compose.local.diff\n"
                " M core/operator/actions/status_report.py\n"
                "?? generated-sites/demo/index.html\n"
            ),
        )  # type: ignore[return-value]

    monkeypatch.setattr(status_report_module, "_run_git", _fake_run_git)

    result = operator_status_report(action_id="OP-STATUS-2", repo_root=tmp_path)

    assert result.status == "success"
    assert result.data["branch"] == "code22/split-answer-contract"
    assert result.data["ahead"] == 2
    assert result.data["behind"] == 0
    assert result.data["sync"] == "ahead"
    assert result.data["clean"] is False
    assert result.data["repo_files"] == ["core/operator/actions/status_report.py"]
    assert result.data["local_only_files"] == [
        "docker-compose.yml",
        "docker-compose.local.diff",
    ]
    assert result.data["sandbox_files"] == ["generated-sites/demo/index.html"]
    assert result.data["protected_local_only_files"] == [
        "docker-compose.yml",
        "docker-compose.local.diff",
    ]
    assert "docker compose config" in result.data["validation_commands"]
    assert result.data["docker_compose_config_recommended"] is True
    assert "approval required" in result.data["repo_write_policy"]
    assert "sandbox root" in result.data["sandbox_write_policy"]
    assert result.data["commit_push_waiting_for_approval"] is True
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_operator_status_report_reports_git_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(
        _root: Path, _args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return _Proc(128, "", "fatal: not a git repository")  # type: ignore[return-value]

    monkeypatch.setattr(status_report_module, "_run_git", _fake_run_git)

    result = operator_status_report(action_id="OP-STATUS-3", repo_root=tmp_path)

    assert result.status == "failed"
    assert result.exit_code == 128
    assert "runtime repo root is not a usable git workspace" in result.stderr_summary
    assert result.safety.read_only is True
    assert result.safety.allowed is True


def test_operator_status_report_sanitizes_not_git_repo_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(
        _root: Path, _args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return _Proc(
            128,
            "",
            "fatal: not a git repository: /workspace/X:/XV7/xv7/.git/worktrees/xv7-fix-live-smoke",
        )  # type: ignore[return-value]

    monkeypatch.setattr(status_report_module, "_run_git", _fake_run_git)

    result = operator_status_report(action_id="OP-STATUS-5", repo_root=tmp_path)

    assert result.status == "failed"
    assert "runtime repo root is not a usable git workspace" in result.stderr_summary
    assert "/workspace/X:/XV7" not in result.stderr_summary


def test_operator_status_report_is_available_through_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(
        _root: Path, _args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return _Proc(0, "## main...origin/main\n")  # type: ignore[return-value]

    monkeypatch.setattr(status_report_module, "_run_git", _fake_run_git)

    result = run_action(
        "operator_status_report",
        action_id="OP-STATUS-4",
        repo_root=tmp_path,
    )

    assert result.status == "success"
    assert result.action_name == "operator_status_report"
