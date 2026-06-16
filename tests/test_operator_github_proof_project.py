from __future__ import annotations

import json
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
    monkeypatch.setenv("XV7_GIT_USER_NAME", "XV7 Bot")
    monkeypatch.setenv("XV7_GIT_USER_EMAIL", "xv7-bot@example.com")

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


def test_existing_repo_without_remote_returns_clear_missing_remote_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

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
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0004",
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
    assert result.data.get("missing_remote") is True
    assert "no GitHub remote" in result.stderr_summary
    assert not any(cmd[:2] == ["gh", "auth"] for cmd in calls)
    assert not any(cmd[:3] == ["gh", "repo", "create"] for cmd in calls)
    assert not any(cmd[:4] == ["git", "push", "-u", "origin"] for cmd in calls)


def test_existing_origin_pushes_directly_without_remote_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

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
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        if args[:4] == ["git", "push", "-u", "origin"]:
            return _Proc(args, 0, stdout="pushed")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0005",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": True,
            "push": True,
        },
    )

    assert result.status == "success"
    assert result.data.get("pushed") is True
    assert not any(cmd[:3] == ["gh", "auth", "status"] for cmd in calls)
    assert not any(cmd[:3] == ["gh", "repo", "create"] for cmd in calls)


def test_existing_github_repo_is_connected_when_create_reports_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    calls: list[list[str]] = []
    state = {"remote_added": False}

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
            if state["remote_added"]:
                return _Proc(
                    args,
                    0,
                    stdout="origin\thttps://github.com/example/earthx-github-proof.git (fetch)\n",
                )  # type: ignore[return-value]
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        if args[:3] == ["gh", "auth", "status"]:
            return _Proc(args, 0, stdout="ok")  # type: ignore[return-value]
        if args[:3] == ["gh", "repo", "create"]:
            return _Proc(args, 1, stderr="GraphQL: name already exists on this account")  # type: ignore[return-value]
        if args[:3] == ["gh", "repo", "view"]:
            return _Proc(
                args,
                0,
                stdout="https://github.com/example/earthx-github-proof\n",
            )  # type: ignore[return-value]
        if args[:4] == ["git", "remote", "add", "origin"]:
            state["remote_added"] = True
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "push", "-u", "origin"]:
            return _Proc(args, 0, stdout="pushed")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0006",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": True,
            "push": True,
        },
    )

    assert result.status == "success"
    assert result.data.get("remote_url", "").startswith("https://github.com/")
    assert any(cmd[:3] == ["gh", "repo", "create"] for cmd in calls)
    assert any(cmd[:4] == ["git", "remote", "add", "origin"] for cmd in calls)


def test_missing_gh_reports_clear_repo_creation_requirement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    def _fake_run_command(
        _cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return _Proc(args, 0, stdout="true\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return _Proc(args, 0, stdout="main\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--short"]:
            return _Proc(args, 0, stdout="abc1234\n")  # type: ignore[return-value]
        if args[:3] == ["git", "remote", "-v"]:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        if args[:2] == ["gh", "--version"]:
            return _Proc(args, 127, stderr="command not found: gh")  # type: ignore[return-value]
        return _Proc(args, 0)  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0007",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": True,
            "push": True,
        },
    )

    assert result.status == "failed"
    assert result.data.get("failed_command") == "gh --version"
    assert result.data.get("gh_missing") is True
    assert result.exit_code == 127
    assert "GitHub CLI is not installed" in result.stderr_summary


def test_missing_git_identity_uses_durable_profile_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )
    monkeypatch.delenv("XV7_GIT_USER_NAME", raising=False)
    monkeypatch.delenv("XV7_GIT_USER_EMAIL", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_EMAIL", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_EMAIL", raising=False)

    calls: list[list[str]] = []

    def _fake_run_command(
        _cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return _Proc(args, 1, stderr="not a git repo")  # type: ignore[return-value]
        if args[:3] == ["git", "init", "-b"]:
            return _Proc(args, 0, stdout="Initialized")  # type: ignore[return-value]
        if args[:2] == ["git", "config"] and "--get" in args:
            return _Proc(args, 1, stderr="")  # type: ignore[return-value]
        return _Proc(args, 0, stdout="")  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0008",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "requested_files": ["index.html"],
            "initialize_git": True,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "success"
    configured_name = [
        cmd
        for cmd in calls
        if len(cmd) >= 4 and cmd[:3] == ["git", "config", "user.name"]
    ]
    configured_email = [
        cmd
        for cmd in calls
        if len(cmd) >= 4 and cmd[:3] == ["git", "config", "user.email"]
    ]
    assert configured_name
    assert configured_name[-1][3].strip()
    assert configured_email
    assert configured_email[-1][3].strip()


def test_git_identity_from_env_is_applied_before_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )
    monkeypatch.setenv("XV7_GIT_USER_NAME", "XV7 Bot")
    monkeypatch.setenv("XV7_GIT_USER_EMAIL", "xv7-bot@example.com")

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
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        if args[:2] == ["git", "config"] and "--get" in args:
            return _Proc(args, 1, stderr="")  # type: ignore[return-value]
        if args[:2] == ["git", "config"] and len(args) >= 4:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args == ["git", "add", "."]:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:2] == ["git", "commit"]:
            return _Proc(args, 0, stdout="[main def5678] build GitHub proof project")  # type: ignore[return-value]
        return _Proc(args, 0, stdout="")  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0009",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "requested_files": ["index.html"],
            "initialize_git": True,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "success"
    assert ["git", "config", "user.name", "XV7 Bot"] in calls
    assert ["git", "config", "user.email", "xv7-bot@example.com"] in calls


def test_github_workflow_runs_only_in_sandbox_project_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )

    seen_cwds: list[Path] = []

    def _fake_run_command(
        cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        seen_cwds.append(cwd)
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
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        return _Proc(args, 0, stdout="")  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0010",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "success"
    assert seen_cwds
    assert all(cwd.resolve() == project_path.resolve() for cwd in seen_cwds)
    assert all(cwd.resolve() != tmp_path.resolve() for cwd in seen_cwds)


def test_github_workflow_persists_durable_publish_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)
    profile_path = tmp_path / "github_publish_profile.json"

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )
    monkeypatch.setenv("XV7_GITHUB_PUBLISH_PROFILE_PATH", str(profile_path))

    def _fake_run_command(
        _cwd: Path, args: list[str]
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return _Proc(args, 0, stdout="true\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return _Proc(args, 0, stdout="main\n")  # type: ignore[return-value]
        if args[:3] == ["git", "rev-parse", "--short"]:
            return _Proc(args, 0, stdout="abc1234\n")  # type: ignore[return-value]
        if args[:3] == ["git", "remote", "-v"]:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        return _Proc(args, 0, stdout="")  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0011",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "write_project_files": False,
            "initialize_git": True,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "success"
    assert profile_path.exists()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    assert payload.get("github_owner") == "otiseduncan"
    assert payload.get("proof_repo_url") == (
        "https://github.com/otiseduncan/xv7-sandbox-export-proof-20260614"
    )
    assert result.data.get("publish_profile_source")


def test_git_identity_falls_back_to_durable_publish_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    project_path = sandbox_root / "earthx-github-proof"
    project_path.mkdir(parents=True, exist_ok=True)
    profile_path = tmp_path / "github_publish_profile.json"

    monkeypatch.setattr(
        "core.operator.actions.github_project.SandboxWriteManager.sandbox_root",
        staticmethod(lambda: sandbox_root),
    )
    monkeypatch.setenv("XV7_GITHUB_PUBLISH_PROFILE_PATH", str(profile_path))
    monkeypatch.delenv("XV7_GIT_USER_NAME", raising=False)
    monkeypatch.delenv("XV7_GIT_USER_EMAIL", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_EMAIL", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_EMAIL", raising=False)

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
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:4] == ["git", "status", "--short", "--branch"]:
            return _Proc(args, 0, stdout="## main\n")  # type: ignore[return-value]
        if args[:2] == ["git", "config"] and "--get" in args:
            return _Proc(args, 1, stderr="")  # type: ignore[return-value]
        if args[:2] == ["git", "config"] and len(args) >= 4:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args == ["git", "add", "."]:
            return _Proc(args, 0, stdout="")  # type: ignore[return-value]
        if args[:2] == ["git", "commit"]:
            return _Proc(args, 0, stdout="[main def5678] build GitHub proof project")  # type: ignore[return-value]
        return _Proc(args, 0, stdout="")  # type: ignore[return-value]

    monkeypatch.setattr(
        "core.operator.actions.github_project._run_command",
        _fake_run_command,
    )

    result = operator_github_proof_project(
        action_id="OP-TEST-0012",
        repo_root=tmp_path,
        request={
            "project_name": "earthx-github-proof",
            "project_path": str(project_path),
            "requested_files": ["index.html"],
            "initialize_git": True,
            "create_github_repo": False,
            "push": False,
        },
    )

    assert result.status == "success"
    assert ["git", "config", "user.name", "Otis Duncan"] in calls
    assert ["git", "config", "user.email", "otiseduncan@gmail.com"] in calls
