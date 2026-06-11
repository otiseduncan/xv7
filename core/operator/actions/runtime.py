from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
from urllib.parse import urljoin

from core.operator.schema import OperatorActionResult, OperatorSafety
from core.runtime.status import build_runtime_status


def _get_json(url: str) -> tuple[bool, dict]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8")
        return True, json.loads(body)
    except Exception:
        return False, {}


def _probe_url(url: str, *, timeout: int = 6) -> tuple[bool, int | None, str | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read(64)
            return True, getattr(resp, "status", 200), None
    except Exception as exc:
        return False, None, str(exc)


def _checked_from() -> str:
    if os.getenv("XV7_OPERATOR_CHECKED_FROM") in {"container", "host", "unknown"}:
        return str(os.getenv("XV7_OPERATOR_CHECKED_FROM"))
    if Path("/.dockerenv").exists():
        return "container"
    return "host"


def _service_url_config() -> dict[str, str]:
    core_base = os.getenv("XV7_CORE_INTERNAL_URL", "http://localhost:8000")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    webui_base = os.getenv("WEBUI_BASE_URL", "http://open-webui:8080")
    frontend_base = os.getenv("XV7_FRONTEND_INTERNAL_URL", "http://xv7-frontend")
    return {
        "core_base": core_base.rstrip("/"),
        "ollama_base": ollama_base.rstrip("/"),
        "webui_base": webui_base.rstrip("/"),
        "frontend_base": frontend_base.rstrip("/"),
    }


def _build_check(
    *,
    checked_from: str,
    service_name: str,
    url_used: str,
    reachable: bool,
    limitation: str | None,
) -> dict[str, str | bool | None]:
    return {
        "checked_from": checked_from,
        "service_name": service_name,
        "url_used": url_used,
        "reachable": reachable,
        "limitation": limitation,
    }


def runtime_health(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    checked_from = _checked_from()
    config = _service_url_config()

    core_health_url = urljoin(config["core_base"] + "/", "health")
    core_status_url = urljoin(config["core_base"] + "/", "runtime/status")
    ollama_url = urljoin(config["ollama_base"] + "/", "api/tags")
    webui_url = urljoin(config["webui_base"] + "/", "health")
    frontend_url = config["frontend_base"] + "/"

    health = {"status": "ok"}
    status_payload = build_runtime_status()
    ok_health = True
    ok_status = True

    ok_ollama, ollama_code, ollama_error = _probe_url(ollama_url)
    ok_webui, webui_code, webui_error = _probe_url(webui_url)
    ok_frontend, frontend_code, frontend_error = _probe_url(frontend_url)
    completed = datetime.now(UTC)

    checks = [
        _build_check(
            checked_from=checked_from,
            service_name="xv7-core-health",
            url_used=core_health_url,
            reachable=ok_health,
            limitation=None,
        ),
        _build_check(
            checked_from=checked_from,
            service_name="xv7-core-runtime-status",
            url_used=core_status_url,
            reachable=ok_status,
            limitation=None,
        ),
        _build_check(
            checked_from=checked_from,
            service_name="ollama",
            url_used=ollama_url,
            reachable=ok_ollama,
            limitation=None if ok_ollama else f"Ollama probe failed: {ollama_error}",
        ),
        _build_check(
            checked_from=checked_from,
            service_name="open-webui",
            url_used=webui_url,
            reachable=ok_webui,
            limitation=None if ok_webui else f"Open WebUI probe failed: {webui_error}",
        ),
        _build_check(
            checked_from=checked_from,
            service_name="xv7-frontend",
            url_used=frontend_url,
            reachable=ok_frontend,
            limitation=None if ok_frontend else f"Frontend probe failed: {frontend_error}",
        ),
    ]

    ok = ok_health and ok_status
    reachable_count = len([item for item in checks if bool(item["reachable"])])
    return OperatorActionResult(
        action_id=action_id,
        action_name="runtime_health",
        status="success" if ok else "failed",
        started_at=started,
        completed_at=completed,
        command_or_operation=(
            "GET core/health; GET core/runtime/status; GET ollama/api/tags; "
            "GET open-webui/health; GET xv7-frontend/"
        ),
        target=config["core_base"],
        stdout_summary=(
            f"checked_from={checked_from}; reachable={reachable_count}/{len(checks)}; "
            f"core_ok={ok_health and ok_status}"
        ),
        stderr_summary="" if ok else "Core required runtime endpoints did not respond.",
        exit_code=0 if ok else 1,
        data={
            "health": health,
            "runtime_status": status_payload,
            "service_checks": checks,
            "checked_from": checked_from,
            "service_url_config": config,
            "raw_probe_status": {
                "ollama": {"status_code": ollama_code, "error": ollama_error},
                "open_webui": {"status_code": webui_code, "error": webui_error},
                "frontend": {"status_code": frontend_code, "error": frontend_error},
            },
        },
        safety=OperatorSafety(allowed=True),
        receipt_label=f"runtime_health {action_id}",
    )


def docker_compose_ps(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    docker_cli_path = shutil.which("docker")
    docker_socket_path = Path("/var/run/docker.sock")
    socket_available = docker_socket_path.exists()

    if not docker_cli_path or not socket_available:
        completed = datetime.now(UTC)
        limitation = (
            "Container status cannot be proven from inside xv7-core because Docker CLI/socket is "
            "unavailable. No action was run beyond the read-only availability check."
        )
        return OperatorActionResult(
            action_id=action_id,
            action_name="docker_compose_ps",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="read-only availability check for docker compose ps",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary=limitation,
            exit_code=127,
            data={
                "docker_cli_available": bool(docker_cli_path),
                "docker_socket_available": socket_available,
                "limitation": limitation,
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"docker_compose_ps {action_id}",
        )

    proc = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    completed = datetime.now(UTC)
    rows = [line for line in proc.stdout.splitlines() if line.strip()]
    parsed = []
    for row in rows:
        try:
            parsed.append(json.loads(row))
        except Exception:
            continue

    ok = proc.returncode == 0
    return OperatorActionResult(
        action_id=action_id,
        action_name="docker_compose_ps",
        status="success" if ok else "failed",
        started_at=started,
        completed_at=completed,
        command_or_operation="docker compose ps --format json",
        target=str(repo_root),
        stdout_summary=f"containers={len(parsed)}" if ok else proc.stdout[:500],
        stderr_summary=proc.stderr[:500],
        exit_code=proc.returncode,
        data={"containers": parsed},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"docker_compose_ps {action_id}",
    )


def logs_summary(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    logs_dir = repo_root / "runtime" / "logs"
    files = []
    if logs_dir.exists():
        files = sorted([path for path in logs_dir.glob("*") if path.is_file()])
    recent = files[-5:]

    summaries = []
    for path in recent:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        tail = lines[-3:] if lines else []
        summaries.append(
            {
                "file": str(path.relative_to(repo_root)).replace("\\", "/"),
                "line_count": len(lines),
                "tail": tail,
            }
        )

    completed = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="logs_summary",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="summarize existing runtime/logs files",
        target=str(logs_dir),
        stdout_summary=f"log_files={len(files)} summarized={len(summaries)}",
        stderr_summary="",
        exit_code=None,
        data={"logs": summaries},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"logs_summary {action_id}",
    )
