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
