from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from core.operator.schema import OperatorActionResult, OperatorSafety


def _bridge_base_url() -> str:
    return os.getenv("XV7_LOCAL_BRIDGE_URL", "http://host.docker.internal:8765").rstrip("/")


def _bridge_token() -> str:
    return os.getenv("XV7_LOCAL_BRIDGE_TOKEN", "xv7-local-bridge-token")


def _bridge_timeout_seconds() -> float:
    raw = os.getenv("XV7_LOCAL_BRIDGE_TIMEOUT_SECONDS", "10")
    try:
        value = float(raw)
    except ValueError:
        return 10.0
    return min(max(value, 2.0), 60.0)


def _safe_preview(data: Any) -> str:
    if isinstance(data, dict):
        keys = ", ".join(sorted(str(k) for k in data.keys())[:8])
        return f"Bridge data keys: {keys}" if keys else "Bridge returned an empty object."
    if isinstance(data, list):
        return f"Bridge returned {len(data)} items."
    if data is None:
        return "Bridge returned no data."
    return str(data)[:320]


def _build_result(
    *,
    action_id: str,
    action_name: str,
    status: str,
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    data: dict[str, Any],
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        mode="read_only",
        status=status,
        started_at=now,
        completed_at=now,
        command_or_operation=command,
        target=str(data.get("repo_root") or "host"),
        stdout_summary=stdout,
        stderr_summary=stderr,
        exit_code=exit_code,
        data=data,
        safety=OperatorSafety(
            allowed=True,
            read_only=True,
            mutates_files=False,
            mutates_git=False,
            mutates_runtime=False,
        ),
        receipt_label=f"{action_name} {action_id}",
    )


def _run_bridge_scan(
    *,
    action_id: str,
    action_name: str,
    repo_root: Path,
    scan_name: str,
) -> OperatorActionResult:
    url = f"{_bridge_base_url()}/scan/{scan_name}"
    command = f"POST {url}"
    headers = {"X-XV7-Bridge-Token": _bridge_token()}

    try:
        with httpx.Client(timeout=_bridge_timeout_seconds()) as client:
            response = client.post(url, headers=headers)
    except httpx.HTTPError as exc:
        return _build_result(
            action_id=action_id,
            action_name=action_name,
            status="failed",
            command=command,
            stdout="",
            stderr=(
                "Local host scan bridge is not running or unreachable. "
                "Start the local bridge service to enable host-level scans. "
                f"Details: {exc}"
            ),
            exit_code=503,
            data={
                "bridge_available": False,
                "bridge_url": _bridge_base_url(),
                "repo_root": str(repo_root),
                "scan": scan_name,
                "limitation": "Local host scan bridge is not running.",
            },
        )

    if response.status_code in {401, 403}:
        return _build_result(
            action_id=action_id,
            action_name=action_name,
            status="failed",
            command=command,
            stdout="",
            stderr="Local host scan bridge token rejected.",
            exit_code=response.status_code,
            data={
                "bridge_available": True,
                "bridge_url": _bridge_base_url(),
                "repo_root": str(repo_root),
                "scan": scan_name,
                "limitation": "Bridge token invalid. Check XV7_LOCAL_BRIDGE_TOKEN.",
            },
        )

    if response.status_code >= 500:
        return _build_result(
            action_id=action_id,
            action_name=action_name,
            status="failed",
            command=command,
            stdout="",
            stderr=f"Local host scan bridge returned {response.status_code}.",
            exit_code=response.status_code,
            data={
                "bridge_available": True,
                "bridge_url": _bridge_base_url(),
                "repo_root": str(repo_root),
                "scan": scan_name,
                "limitation": "Bridge failed to complete host scan.",
            },
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {
            "status": "failed",
            "summary": "Bridge returned non-JSON response.",
            "data": {},
            "stderr": response.text[:1200],
            "exit_code": response.status_code,
        }

    status = str(payload.get("status") or "failed").lower()
    raw_data = payload.get("data")
    result_data = raw_data if isinstance(raw_data, (dict, list)) else {}
    stderr = str(payload.get("stderr") or "")
    summary = str(payload.get("summary") or "")

    exit_code_raw = payload.get("exit_code")
    try:
        exit_code = int(exit_code_raw) if exit_code_raw is not None else (0 if status == "success" else 1)
    except (TypeError, ValueError):
        exit_code = 0 if status == "success" else 1

    merged_data: dict[str, Any] = {
        "bridge_available": True,
        "bridge_url": _bridge_base_url(),
        "repo_root": str(repo_root),
        "scan": scan_name,
        "truncated": bool(payload.get("truncated")),
        "result": result_data,
    }

    if status == "success":
        return _build_result(
            action_id=action_id,
            action_name=action_name,
            status="success",
            command=command,
            stdout=summary or _safe_preview(result_data),
            stderr=stderr[:1200],
            exit_code=exit_code,
            data=merged_data,
        )

    final_stderr = stderr[:1200] if stderr else (summary or "Local host scan bridge failed to complete the request.")
    return _build_result(
        action_id=action_id,
        action_name=action_name,
        status="failed",
        command=command,
        stdout=_safe_preview(result_data),
        stderr=final_stderr,
        exit_code=exit_code,
        data=merged_data,
    )


def scan_system(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_system", repo_root=repo_root, scan_name="system")


def scan_cpu(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_cpu", repo_root=repo_root, scan_name="cpu")


def scan_gpu(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_gpu", repo_root=repo_root, scan_name="gpu")


def scan_disk(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_disk", repo_root=repo_root, scan_name="disk")


def scan_network(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_network", repo_root=repo_root, scan_name="network")


def scan_ports(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_ports", repo_root=repo_root, scan_name="ports")


def scan_processes(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_processes", repo_root=repo_root, scan_name="processes")


def scan_services(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_services", repo_root=repo_root, scan_name="services")


def scan_docker(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_docker", repo_root=repo_root, scan_name="docker")


def scan_vscode(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    return _run_bridge_scan(action_id=action_id, action_name="scan_vscode", repo_root=repo_root, scan_name="vscode")
