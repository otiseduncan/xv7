from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

from core.operator.actions.apply_patch import apply_approved_patch
from core.operator.actions.environment import operator_environment
from core.operator.actions.files import list_project_files, read_project_file
from core.operator.actions.host_scan import (
    scan_cpu,
    scan_disk,
    scan_docker,
    scan_gpu,
    scan_network,
    scan_ports,
    scan_processes,
    scan_services,
    scan_system,
    scan_vscode,
)
from core.operator.actions.memory import memory_audit
from core.operator.actions.repo import repo_recent_commits, repo_status
from core.operator.actions.runtime import (
    docker_compose_ps,
    logs_summary,
    runtime_health,
)
from core.operator.actions.patch_plan import patch_plan
from core.operator.actions.test_runner import test_runner
from core.operator.actions.workspace import workspace_map
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
        "workspace_map": OperatorActionSpec(
            "workspace_map", "read_only", workspace_map
        ),
        "patch_plan": OperatorActionSpec("patch_plan", "read_only", patch_plan),
        "apply_approved_patch": OperatorActionSpec(
            "apply_approved_patch", "operator", apply_approved_patch
        ),
        "test_runner": OperatorActionSpec("test_runner", "read_only", test_runner),
        "list_project_files": OperatorActionSpec(
            "list_project_files", "read_only", list_project_files
        ),
        "read_project_file": OperatorActionSpec(
            "read_project_file", "read_only", read_project_file
        ),
        "runtime_health": OperatorActionSpec(
            "runtime_health", "read_only", runtime_health
        ),
        "docker_compose_ps": OperatorActionSpec(
            "docker_compose_ps", "read_only", docker_compose_ps
        ),
        "operator_environment": OperatorActionSpec(
            "operator_environment", "read_only", operator_environment
        ),
        "scan_system": OperatorActionSpec("scan_system", "read_only", scan_system),
        "scan_cpu": OperatorActionSpec("scan_cpu", "read_only", scan_cpu),
        "scan_gpu": OperatorActionSpec("scan_gpu", "read_only", scan_gpu),
        "scan_disk": OperatorActionSpec("scan_disk", "read_only", scan_disk),
        "scan_network": OperatorActionSpec("scan_network", "read_only", scan_network),
        "scan_ports": OperatorActionSpec("scan_ports", "read_only", scan_ports),
        "scan_processes": OperatorActionSpec(
            "scan_processes", "read_only", scan_processes
        ),
        "scan_services": OperatorActionSpec(
            "scan_services", "read_only", scan_services
        ),
        "scan_docker": OperatorActionSpec("scan_docker", "read_only", scan_docker),
        "scan_vscode": OperatorActionSpec("scan_vscode", "read_only", scan_vscode),
        "logs_summary": OperatorActionSpec("logs_summary", "read_only", logs_summary),
        "memory_audit": OperatorActionSpec("memory_audit", "read_only", memory_audit),
    }


def _target_json(target: str | None, action_name: str) -> dict:
    if not target:
        raise ValueError(f"{action_name} requires a target JSON payload")
    try:
        payload = json.loads(target)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{action_name} target must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{action_name} target JSON must be an object")
    return payload


def _test_runner_payload(target: str | None) -> dict:
    if not target:
        return {"preset": "ci_core"}
    try:
        payload = json.loads(target)
    except json.JSONDecodeError:
        return {"preset": target}
    if not isinstance(payload, dict):
        raise ValueError("test_runner target JSON must be an object")
    return payload


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
    if action_name == "patch_plan":
        if not target:
            raise ValueError("patch_plan requires a target goal")
        return spec.handler(action_id=action_id, repo_root=repo_root, goal=target)
    if action_name == "apply_approved_patch":
        payload = _target_json(target, action_name)
        return spec.handler(action_id=action_id, repo_root=repo_root, patch=payload)
    if action_name == "test_runner":
        payload = _test_runner_payload(target)
        return spec.handler(
            action_id=action_id,
            repo_root=repo_root,
            preset=str(payload.get("preset", "ci_core")),
            test_target=payload.get("test_target"),
            timeout_seconds=int(payload.get("timeout_seconds", 120)),
        )
    return spec.handler(action_id=action_id, repo_root=repo_root)
