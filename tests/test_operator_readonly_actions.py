from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess

import pytest

from core.operator.actions.environment import operator_environment
from core.operator.actions.files import read_project_file
from core.operator.actions.memory import memory_audit
from core.operator.actions.repo import repo_status
from core.operator.actions.runtime import docker_compose_ps, runtime_health
from core.operator.manager import OperatorManager


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _ok_json(_url: str) -> tuple[bool, dict]:
    return True, {"status": "ok"}


def test_repo_status_receipt_and_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _Proc(0, "main\n")  # type: ignore[return-value]
        if args == ["status", "--porcelain"]:
            return _Proc(0, "")  # type: ignore[return-value]
        if args == ["status", "--porcelain", "--branch"]:
            return _Proc(0, "## main...origin/main\n")  # type: ignore[return-value]
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Proc(0, "origin/main\n")  # type: ignore[return-value]
        return _Proc(1, "", "unexpected")  # type: ignore[return-value]

    monkeypatch.setattr("core.operator.actions.repo._run_git", _fake_run_git)

    result = repo_status(action_id="OP-20260611-0001", repo_root=tmp_path)
    assert result.status == "success"
    assert result.safety.allowed is True
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.safety.mutates_runtime is False
    assert "Operator receipt:" in result.receipt()


def test_repo_status_handles_missing_git_binary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _raise_missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("core.operator.actions.repo.subprocess.run", _raise_missing_git)

    result = repo_status(action_id="OP-20260611-0099", repo_root=tmp_path)
    assert result.status == "failed"
    assert result.exit_code == 127
    assert "git executable not found" in result.stderr_summary
    assert result.safety.allowed is True
    assert result.safety.read_only is True


def test_read_project_file_denies_outside_repo_root(tmp_path: Path) -> None:
    inside = tmp_path / "safe.txt"
    inside.write_text("ok", encoding="utf-8")

    result = read_project_file(
        action_id="OP-20260611-0002",
        repo_root=tmp_path,
        path="../outside.txt",
    )
    assert result.status == "denied"
    assert result.safety.allowed is False
    assert result.safety.denial_reason == "outside_repo_root"


def test_operator_manager_denies_mutation_request() -> None:
    manager = OperatorManager(repo_root=Path.cwd())
    handled = manager.try_handle_chat("Please delete runtime logs")

    assert handled is not None
    assert handled.result.status == "denied"
    assert "read-only" in handled.answer.lower()


def test_operator_manager_allows_prompt_writing_requests() -> None:
    manager = OperatorManager(repo_root=Path.cwd())
    handled = manager.try_handle_chat(
        "Can you help write implementation prompts for VS Code/Copilot?"
    )

    assert handled is None


def test_operator_manager_allows_vs_code_prompt_generation_request() -> None:
    manager = OperatorManager(repo_root=Path.cwd())
    handled = manager.try_handle_chat("Write a VS Code prompt for B8.2")

    assert handled is None


@pytest.mark.parametrize(
    "prompt",
    [
        "Commit the changes",
        "Restart Docker",
        "Delete a file",
    ],
)
def test_operator_manager_keeps_mutation_denials(prompt: str) -> None:
    manager = OperatorManager(repo_root=Path.cwd())
    handled = manager.try_handle_chat(prompt)

    assert handled is not None
    assert handled.result.status == "denied"


def test_runtime_health_operation_is_get_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.operator.actions.runtime._get_json", _ok_json)
    monkeypatch.setattr(
        "core.operator.actions.runtime._probe_url",
        lambda _url, timeout=6: (True, 200, None),
    )

    result = runtime_health(action_id="OP-20260611-0003", repo_root=tmp_path)
    assert result.status == "success"
    operation = result.command_or_operation.upper()
    assert "GET" in operation
    assert "POST" not in operation
    assert "PUT" not in operation
    assert "DELETE" not in operation
    checks = result.data.get("service_checks", [])
    assert checks
    assert all(item.get("checked_from") in {"container", "host", "unknown"} for item in checks)
    assert all("url_used" in item for item in checks)
    assert all("service_name" in item for item in checks)
    assert all("reachable" in item for item in checks)
    assert all("limitation" in item for item in checks)


def test_runtime_health_prefers_internal_urls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("WEBUI_BASE_URL", "http://open-webui:8080")
    monkeypatch.setenv("XV7_FRONTEND_INTERNAL_URL", "http://xv7-frontend")
    monkeypatch.setattr("core.operator.actions.runtime._get_json", _ok_json)
    monkeypatch.setattr(
        "core.operator.actions.runtime._probe_url",
        lambda _url, timeout=6: (True, 200, None),
    )

    result = runtime_health(action_id="OP-20260611-0100", repo_root=tmp_path)
    checks = result.data.get("service_checks", [])
    by_service = {
        item.get("service_name"): item.get("url_used")
        for item in checks
        if isinstance(item, dict)
    }
    assert by_service.get("ollama", "").startswith("http://ollama:11434")
    assert by_service.get("open-webui", "").startswith("http://open-webui:8080")
    assert by_service.get("xv7-frontend", "").startswith("http://xv7-frontend")


def test_docker_compose_ps_unavailable_is_honest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.operator.actions.runtime.shutil.which", lambda _name: None)

    result = docker_compose_ps(action_id="OP-20260611-0101", repo_root=tmp_path)
    assert result.status == "failed"
    assert "Container status cannot be proven" in result.stderr_summary
    assert result.data.get("docker_cli_available") is False
    assert result.data.get("docker_socket_available") is False


def test_operator_environment_reports_capabilities(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(
        "core.operator.actions.environment.shutil.which",
        lambda name: "/usr/bin/tool" if name in {"git", "docker"} else None,
    )

    result = operator_environment(action_id="OP-20260611-0102", repo_root=tmp_path)
    assert result.status == "success"
    assert result.data.get("repo_root") == str(tmp_path)
    assert result.data.get("read_only_mode") is True
    assert "service_url_config" in result.data
    assert "memory_store_path" in result.data


def test_memory_audit_action_is_read_only(tmp_path: Path) -> None:
    result = memory_audit(action_id="OP-20260611-0004", repo_root=tmp_path)

    assert result.status == "success"
    assert result.safety.allowed is True
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.safety.mutates_runtime is False
    assert isinstance(result.data, dict)
    assert "total_records" in result.data
