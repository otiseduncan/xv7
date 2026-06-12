from __future__ import annotations

from pathlib import Path

import pytest

from core.operator.registry import build_operator_registry, run_action


EXPECTED_ACTIONS = {
    "repo_status",
    "repo_recent_commits",
    "workspace_map",
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


def test_operator_registry_contains_expected_read_only_actions() -> None:
    registry = build_operator_registry()

    assert set(registry.keys()) == EXPECTED_ACTIONS
    assert all(spec.mode == "read_only" for spec in registry.values())


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
