from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions import repo as repo_actions
from core.operator.actions.repo import operator_commit_report


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_preview_mode_reports_candidates_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert args == ["status", "--short", "--branch"]
        return _Proc(
            0,
            (
                "## code22/split-answer-contract...origin/code22/split-answer-contract\n"
                " M core/operator/actions/repo.py\n"
                " M docker-compose.yml\n"
                "?? .env\n"
            ),
        )  # type: ignore[return-value]

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-1",
        repo_root=tmp_path,
        request={"mode": "preview", "summary": "operator commit lane"},
    )

    assert result.status == "success"
    assert result.data["candidate_files"] == ["core/operator/actions/repo.py"]
    assert "docker-compose.yml" in result.data["skipped_files"]
    assert ".env" in result.data["skipped_files"]
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert calls == [["status", "--short", "--branch"]]


def test_apply_without_commit_approval_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args == ["status", "--short", "--branch"]
        return _Proc(0, "## main...origin/main\n M core/main.py\n")  # type: ignore[return-value]

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-2",
        repo_root=tmp_path,
        request={"mode": "apply", "approval": {"approved": False}},
    )

    assert result.status == "denied"
    assert result.safety.requires_approval is True
    assert result.data["committed_files"] == []
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_apply_with_approval_commits_only_safe_repo_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["status", "--short", "--branch"]:
            return _Proc(
                0,
                (
                    "## code22/split-answer-contract...origin/code22/split-answer-contract\n"
                    " M core/main.py\n"
                    " M public/app.js\n"
                    " M docker-compose.yml\n"
                    "?? .env\n"
                ),
            )  # type: ignore[return-value]
        if args[:2] == ["add", "--"]:
            return _Proc(0, "", "")  # type: ignore[return-value]
        if args[:2] == ["commit", "-m"]:
            return _Proc(
                0,
                "[code22/split-answer-contract abc1234] chore: safe commit\n 2 files changed\n",
                "",
            )  # type: ignore[return-value]
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-3",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": {"approved": True},
            "summary": "safe commit",
            "selected_files": ["public/app.js"],
        },
    )

    assert result.status == "success"
    assert result.data["candidate_files"] == ["public/app.js"]
    assert result.data["committed_files"] == ["public/app.js"]
    assert "docker-compose.yml" in result.data["skipped_files"]
    assert ".env" in result.data["skipped_files"]
    assert result.data["commit_sha"] == "abc1234"
    assert result.data["push_performed"] is False
    assert "No merge was performed." in result.data["safety_notes"]
    assert calls[0] == ["status", "--short", "--branch"]
    assert calls[1] == ["add", "--", "public/app.js"]
    assert calls[2][0:3] == ["commit", "-m", "chore: safe commit"]


def test_push_without_approval_is_blocked_before_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["status", "--short", "--branch"]:
            return _Proc(0, "## main...origin/main\n M core/main.py\n")  # type: ignore[return-value]
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-4",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": {"approved": True},
            "push": True,
            "push_approval": {"approved": False},
        },
    )

    assert result.status == "denied"
    assert result.safety.requires_approval is True
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert calls == [["status", "--short", "--branch"]]


def test_force_push_request_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args == ["status", "--short", "--branch"]
        return _Proc(0, "## main...origin/main\n M core/main.py\n")  # type: ignore[return-value]

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-5",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": {"approved": True},
            "force_push": True,
        },
    )

    assert result.status == "denied"
    assert "Force push" in result.stderr_summary
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_commit_report_sanitizes_not_git_repo_error(
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

    monkeypatch.setattr(repo_actions, "_run_git", _fake_run_git)

    result = operator_commit_report(
        action_id="OP-COMMIT-6",
        repo_root=tmp_path,
        request={"mode": "apply", "approval": {"approved": True}, "push": True},
    )

    assert result.status == "denied"
    assert result.safety.requires_approval is True
    assert "runtime repo root is not a usable git workspace" in result.stderr_summary
    assert "/workspace/X:/XV7" not in result.stderr_summary
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
