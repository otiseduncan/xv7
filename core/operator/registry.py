from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.operator.actions.environment import operator_environment
from core.operator.actions.files import list_project_files, read_project_file
from core.operator.actions.memory import memory_audit
from core.operator.actions.repo import repo_recent_commits, repo_status
from core.operator.actions.runtime import docker_compose_ps, logs_summary, runtime_health
from core.operator.schema import OperatorActionResult


@dataclass(frozen=True)
class OperatorActionSpec:
    name: str
    mode: str
    handler: Callable[..., OperatorActionResult]


def build_operator_registry() -> dict[str, OperatorActionSpec]:
    return {
        "repo_status": OperatorActionSpec("repo_status", "read_only", repo_status),
        "repo_recent_commits": OperatorActionSpec(
            "repo_recent_commits", "read_only", repo_recent_commits
        ),
        "list_project_files": OperatorActionSpec(
            "list_project_files", "read_only", list_project_files
        ),
        "read_project_file": OperatorActionSpec(
            "read_project_file", "read_only", read_project_file
        ),
        "runtime_health": OperatorActionSpec("runtime_health", "read_only", runtime_health),
        "docker_compose_ps": OperatorActionSpec(
            "docker_compose_ps", "read_only", docker_compose_ps
        ),
        "operator_environment": OperatorActionSpec(
            "operator_environment", "read_only", operator_environment
        ),
        "logs_summary": OperatorActionSpec("logs_summary", "read_only", logs_summary),
        "memory_audit": OperatorActionSpec("memory_audit", "read_only", memory_audit),
    }


def run_action(
    action_name: str,
    *,
    action_id: str,
    repo_root: Path,
    target: str | None = None,
) -> OperatorActionResult:
    registry = build_operator_registry()
    if action_name not in registry:
        raise ValueError(f"Unknown operator action: {action_name}")
    spec = registry[action_name]
    if action_name == "read_project_file":
        if not target:
            raise ValueError("read_project_file requires a target path")
        return spec.handler(action_id=action_id, repo_root=repo_root, path=target)
    return spec.handler(action_id=action_id, repo_root=repo_root)
