from __future__ import annotations

import os
from pathlib import Path
import shutil

from datetime import UTC, datetime

from core.operator.schema import OperatorActionResult, OperatorSafety


def operator_environment(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)

    docker_socket_path = Path("/var/run/docker.sock")
    service_url_config = {
        "core_base": os.getenv("XV7_CORE_INTERNAL_URL", "http://localhost:8000"),
        "ollama_base": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        "webui_base": os.getenv("WEBUI_BASE_URL", "http://open-webui:8080"),
        "frontend_base": os.getenv("XV7_FRONTEND_INTERNAL_URL", "http://xv7-frontend"),
    }
    memory_store_path = os.getenv("XV7_PERSISTENT_MEMORY_PATH", "data/memory/records")

    payload = {
        "repo_root": str(repo_root),
        "git_available": bool(shutil.which("git")),
        "docker_cli_available": bool(shutil.which("docker")),
        "docker_socket_available": docker_socket_path.exists(),
        "service_url_config": service_url_config,
        "memory_store_path": memory_store_path,
        "read_only_mode": True,
    }

    completed = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_environment",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="operator environment diagnostics (read-only)",
        target=str(repo_root),
        stdout_summary=(
            f"git_available={payload['git_available']}; "
            f"docker_cli_available={payload['docker_cli_available']}; "
            f"docker_socket_available={payload['docker_socket_available']}"
        ),
        stderr_summary="",
        exit_code=None,
        data=payload,
        safety=OperatorSafety(allowed=True),
        receipt_label=f"operator_environment {action_id}",
    )
