from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions.github_project import operator_github_proof_project


class _Proc:
    def __init__(
        self, args: list[str], returncode: int, stdout: str = "", stderr: str = ""
    ) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_github_proof_project_denies_outside_sandbox(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0001",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(tmp_path / "outside" / "earthx-github-proof"),
            "requested_files": ["index.html"],
            "initialize_git": False,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "denied"
    assert "outside the approved sandbox root" in result.stderr_summary


def test_github_proof_project_reports_exact_failed_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    calls: list[list[str]] = []

    def _fake_run_command(
        _cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ["git", "init", "-b"]:
            return _Proc(args, 0, stdout="Initialized")  # type: ignore[return-value]
        if args == ["git", "add", "."]:
            return _Proc(args, 0)  # type: ignore[return-value]
        if args[:2] == ["git", "commit"]:
            return _Proc(
                args, 0, stdout="[main abc1234] build EarthX GitHub proof site"
            )  # type: ignore[return-value]
        if args[:3] == ["gh", "repo", "create"]:
            return _Proc(args, 1, stderr="authentication required")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0002",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(sandbox_root / "earthx-github-proof"),
            "requested_files": [
                "index.html",
                "assets/site.css",
                "assets/app.js",
                "README.md",
            ],
            "commit_message": "build EarthX GitHub proof site",
            "initialize_git": True,
            "create_github_repo": True,
            "github_repo_name": "earthx-github-proof",
            "push": True,
        },
    )

    assert result.status == "failed"
    assert result.data.get("failed_command", "").startswith("gh repo create")
    assert "authentication required" in result.stderr_summary
    assert any(cmd[:3] == ["gh", "repo", "create"] for cmd in calls)


def test_finish_push_existing_project_reports_repo_state_and_exact_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "README.md").write_text("existing\n", encoding="utf-8")

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    calls: list[list[str]] = []

    def _fake_run_command(
        _cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return _Proc(args, 0, stdout="true\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return _Proc(args, 0, stdout="main\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--short"]:
            return _Proc(args, 0, stdout="abc1234\n")  # type: ignore[return-value]
        if args[:3] == ["git", "remote", "-v"]:
            return _Proc(
                args,
                0,
                stdout="origin\thttps://github.com/example/earthx-github-proof.git (fetch)\n",
            )  # type: ignore[return-value]
        if args[:3] == ["git", "status", "--porcelain"]:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "push", "-u", "origin"]:
            return _Proc(args, 1, stderr="authentication failed")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0003",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": False,
            "push": True,
        },
    )

    assert result.status == "failed"
    assert result.data.get("failed_command") == "git push -u origin main"
    repo_before = result.data.get("repo_before", {})
    assert repo_before.get("branch") == "main"
    assert isinstance(repo_before.get("remotes"), list)
    assert any(cmd[:4] == ["git", "push", "-u", "origin"] for cmd in calls)
