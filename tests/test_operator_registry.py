from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from core.operator.registry import build_operator_registry, run_action


EXPECTED_ACTIONS = {
    "repo_status",
    "repo_recent_commits",
    "operator_status_report",
    "operator_validation_report",
    "operator_patch_report",
    "operator_repair_report",
    "workspace_map",
    "patch_plan",
    "apply_approved_patch",
    "test_runner",
    "diff_report",
    "list_project_files",
    "read_project_file",
    "runtime_health",
    "docker_compose_ps",
    "operator_environment",
    "scan_system",
    "scan_cpu",
    "scan_gpu",
    "scan_disk",
    "scan_network",
    "scan_ports",
    "scan_processes",
    "scan_services",
    "scan_docker",
    "scan_vscode",
    "logs_summary",
    "memory_audit",
}


class FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_operator_registry_contains_expected_actions() -> None:
    registry = build_operator_registry()

    assert set(registry.keys()) == EXPECTED_ACTIONS
    assert registry["apply_approved_patch"].mode == "operator"
    operator_actions = {
        "apply_approved_patch",
        "operator_patch_report",
        "operator_repair_report",
    }
    assert all(
        spec.mode == "read_only"
        for name, spec in registry.items()
        if name not in operator_actions
    )


def test_run_action_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unknown operator action"):
        run_action(
            "not_a_real_action",
            action_id="OP-20260611-0001",
            repo_root=Path.cwd(),
        )


def test_run_action_requires_target_for_read_project_file() -> None:
    with pytest.raises(ValueError, match="requires a target path"):
        run_action(
            "read_project_file",
            action_id="OP-20260611-0002",
            repo_root=Path.cwd(),
            target=None,
        )


def test_run_action_patch_plan_with_goal() -> None:
    result = run_action(
        "patch_plan",
        action_id="OP-20260611-0003",
        repo_root=Path.cwd(),
        target="Implement CODE-02 Patch Planner",
    )
    assert result.status == "success"
    assert result.action_name == "patch_plan"


def test_run_action_patch_plan_requires_target() -> None:
    with pytest.raises(ValueError, match="requires a target goal"):
        run_action(
            "patch_plan",
            action_id="OP-20260611-0004",
            repo_root=Path.cwd(),
            target=None,
        )


def test_run_action_apply_approved_patch_with_json_payload(tmp_path: Path) -> None:
    payload = {
        "approval": {"approved": True, "approval_id": "APP-1"},
        "source_plan_id": "PLAN-1",
        "risk": "low",
        "changes": [{"path": "docs/example.md", "content": "hello\n"}],
    }

    result = run_action(
        "apply_approved_patch",
        action_id="OP-20260611-0005",
        repo_root=tmp_path,
        target=json.dumps(payload),
    )

    assert result.status == "success"
    assert result.action_name == "apply_approved_patch"
    assert result.data["changed_files"] == ["docs/example.md"]
    assert (tmp_path / "docs" / "example.md").read_text(encoding="utf-8") == "hello\n"


def test_run_action_apply_approved_patch_requires_json_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a target JSON payload"):
        run_action(
            "apply_approved_patch",
            action_id="OP-20260611-0006",
            repo_root=tmp_path,
            target=None,
        )


def test_run_action_apply_approved_patch_rejects_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="target must be valid JSON"):
        run_action(
            "apply_approved_patch",
            action_id="OP-20260611-0007",
            repo_root=tmp_path,
            target="not-json",
        )


def test_run_action_test_runner_with_json_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        return FakeCompletedProcess(0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_action(
        "test_runner",
        action_id="OP-20260611-0008",
        repo_root=tmp_path,
        target=json.dumps(
            {
                "preset": "single_pytest",
                "test_target": "tests/test_operator_registry.py::test_operator_registry_contains_expected_actions",
            }
        ),
    )

    assert result.status == "success"
    assert result.action_name == "test_runner"
    assert result.data["passed"] is True


def test_run_action_test_runner_accepts_plain_preset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(_command: list[str], **_kwargs: object) -> FakeCompletedProcess:
        return FakeCompletedProcess(0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_action(
        "test_runner",
        action_id="OP-20260611-0009",
        repo_root=tmp_path,
        target="lint_backend",
    )

    assert result.status == "success"
    assert result.action_name == "test_runner"
    assert result.data["preset"] == "lint_backend"


def test_run_action_test_runner_rejects_non_object_json(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="target JSON must be an object"):
        run_action(
            "test_runner",
            action_id="OP-20260611-0010",
            repo_root=tmp_path,
            target=json.dumps(["ci_core"]),
        )


def test_run_action_diff_report(tmp_path: Path) -> None:
    result = run_action(
        "diff_report",
        action_id="OP-20260611-0011",
        repo_root=tmp_path,
    )

    assert result.status == "failed"
    assert result.action_name == "diff_report"
    assert result.safety.read_only is True
