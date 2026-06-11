from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions.repo import repo_status
from core.operator.actions.runtime import docker_compose_ps, runtime_health


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_repo_status_parses_branch_sync_and_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _Proc(0, "main\n")  # type: ignore[return-value]
        if args == ["status", "--porcelain"]:
            return _Proc(0, " M core/main.py\n?? tests/new_test.py\n")  # type: ignore[return-value]
        if args == ["status", "--porcelain", "--branch"]:
            return _Proc(0, "## main...origin/main [ahead 1]\n M core/main.py\n")  # type: ignore[return-value]
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Proc(0, "origin/main\n")  # type: ignore[return-value]
        return _Proc(1, "", "unexpected")  # type: ignore[return-value]

    monkeypatch.setattr("core.operator.actions.repo._run_git", _fake_run_git)

    result = repo_status(action_id="OP-20260611-0301", repo_root=tmp_path)
    assert result.status == "success"
    assert result.data["branch"] == "main"
    assert result.data["upstream"] == "origin/main"
    assert result.data["sync"] == "ahead"
    assert result.data["clean"] is False
    assert len(result.data["status_lines"]) == 2


def test_repo_status_missing_upstream_is_limitation_not_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _Proc(0, "main\n")  # type: ignore[return-value]
        if args == ["status", "--porcelain"]:
            return _Proc(0, "")  # type: ignore[return-value]
        if args == ["status", "--porcelain", "--branch"]:
            return _Proc(0, "## main\n")  # type: ignore[return-value]
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Proc(128, "", "no upstream configured")  # type: ignore[return-value]
        return _Proc(1, "", "unexpected")  # type: ignore[return-value]

    monkeypatch.setattr("core.operator.actions.repo._run_git", _fake_run_git)

    result = repo_status(action_id="OP-20260611-0302", repo_root=tmp_path)
    assert result.status == "success"
    assert result.data["upstream"] is None
    assert result.data["limitations"]


def test_runtime_health_uses_internal_service_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("WEBUI_BASE_URL", "http://open-webui:8080")
    monkeypatch.setenv("XV7_FRONTEND_INTERNAL_URL", "http://xv7-frontend")
    monkeypatch.setattr(
        "core.operator.actions.runtime._get_json", lambda _url: (True, {"status": "ok"})
    )
    monkeypatch.setattr(
        "core.operator.actions.runtime._probe_url",
        lambda _url, timeout=6: (True, 200, None),
    )

    result = runtime_health(action_id="OP-20260611-0303", repo_root=tmp_path)
    assert result.status == "success"
    checks = result.data["service_checks"]
    urls = {item["service_name"]: item["url_used"] for item in checks}
    assert urls["ollama"].startswith("http://ollama:11434")
    assert urls["open-webui"].startswith("http://open-webui:8080")
    assert urls["xv7-frontend"].startswith("http://xv7-frontend")


def test_docker_compose_ps_availability_check_no_fake_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "core.operator.actions.runtime.shutil.which", lambda _name: None
    )

    result = docker_compose_ps(action_id="OP-20260611-0304", repo_root=tmp_path)
    assert result.status == "failed"
    assert (
        "No action was run beyond the read-only availability check"
        in result.stderr_summary
    )
