"""Safe X Kernel tool result helpers.

This module exposes only allowlisted self-status actions for the XV7/X message
route. It does not evaluate user-provided commands, import host-only scripts,
or execute arbitrary shell commands.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.runtime.schemas import SessionState

ALLOWED_INTENTS = {"diagnose", "readiness", "state", "proof"}
FORBIDDEN_RISKS = {"developer_write", "system_control", "network_control"}
RECEIPT_DIR = Path("data") / "x_inbox" / "receipts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _tail(text: str | None, limit: int = 8000) -> str:
    value = text or ""
    if len(value) <= limit:
        return value
    return value[-limit:]


def _copy_model(model: Any, **updates: Any) -> Any:
    """Copy a Pydantic model across v1/v2 runtimes."""

    model_copy = getattr(model, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=updates)
    copy = getattr(model, "copy", None)
    if callable(copy):
        return copy(update=updates)
    raise TypeError(f"Object does not support Pydantic-style copy: {type(model)!r}")


def _repo_root() -> Path:
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "core" / "main.py").is_file():
            return candidate
    return current


def _receipt_root() -> Path:
    return _repo_root() / RECEIPT_DIR


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_receipt(kind: str, payload: dict[str, Any]) -> tuple[Path, Path]:
    receipts = _receipt_root()
    latest = receipts / f"latest_{kind}.json"
    stamped = receipts / f"{_stamp()}_{kind}.json"
    _save_json(latest, payload)
    _save_json(stamped, payload)
    return latest, stamped


def _check_path(label: str, path: Path) -> dict[str, Any]:
    return {
        "check": label,
        "status": "pass" if path.exists() else "fail",
        "path": str(path),
    }


def _format_checks(checks: list[dict[str, Any]]) -> str:
    passing = [item["check"] for item in checks if item.get("status") == "pass"]
    failing = [item["check"] for item in checks if item.get("status") != "pass"]
    lines = ["Passing:"]
    lines.extend(f"- {item}" for item in passing)
    lines.append("")
    lines.append("Failing:")
    lines.extend(f"- {item}" for item in failing) if failing else lines.append("- none")
    return "\n".join(lines)


def _receipt_writable_check() -> dict[str, Any]:
    path = _receipt_root() / ".x_kernel_write_check"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
        path.unlink(missing_ok=True)
        return {"check": "receipt_writable", "status": "pass", "path": str(path.parent)}
    except OSError as exc:
        return {
            "check": "receipt_writable",
            "status": "fail",
            "path": str(path.parent),
            "error": str(exc),
        }


def _diagnostic_checks() -> list[dict[str, Any]]:
    root = _repo_root()
    return [
        _check_path("repo_root", root),
        _check_path("core_main", root / "core" / "main.py"),
        _check_path("kernel_decision", root / "core" / "x_kernel" / "decision.py"),
        _check_path("kernel_tool_runner", root / "core" / "x_kernel" / "tool_runner.py"),
        _check_path("session_message_route", root / "core" / "api" / "session_message_routes.py"),
        _receipt_writable_check(),
    ]


def _overall_status(checks: list[dict[str, Any]]) -> str:
    return "pass" if all(item.get("status") == "pass" for item in checks) else "fail"


def _run_diagnose() -> dict[str, Any]:
    root = _repo_root()
    checks = _diagnostic_checks()
    status = _overall_status(checks)
    first_blocker = "none" if status == "pass" else "x_kernel_diagnostic_failure"
    payload = {
        "receipt_type": "x_kernel_diagnose",
        "created_at": _utc_now(),
        "overall_status": status,
        "host_runtime": "xv7_api_container",
        "repo_root": str(root),
        "checks": checks,
        "first_blocker": first_blocker,
        "recommended_next_action": "Continue with the next X Kernel build task." if status == "pass" else "Inspect failing X Kernel diagnostic checks.",
    }
    latest, stamped = _write_receipt("diagnose", payload)
    stdout = (
        f"X Kernel Diagnosis: {status.upper()}\n\n"
        f"Runtime: xv7_api_container\n"
        f"Repo: {root}\n\n"
        f"{_format_checks(checks)}\n\n"
        f"First blocker:\n{first_blocker}\n\n"
        f"Recommended next action:\n{payload['recommended_next_action']}\n\n"
        f"Proof:\n{latest}\n"
        f"Saved diagnosis receipt: {stamped}"
    )
    return {
        "status": "completed" if status == "pass" else "failed",
        "returncode": 0 if status == "pass" else 1,
        "stdout": stdout,
        "receipt_path": str(latest),
    }


def _run_readiness() -> dict[str, Any]:
    root = _repo_root()
    checks = _diagnostic_checks()
    diagnosis = _load_json(_receipt_root() / "latest_diagnose.json")
    latest_diagnosis_status = diagnosis.get("overall_status", "unknown")
    status = "pass" if _overall_status(checks) == "pass" else "fail"
    first_blocker = "none" if status == "pass" else "x_kernel_readiness_failure"
    payload = {
        "receipt_type": "x_kernel_readiness",
        "created_at": _utc_now(),
        "readiness_status": status,
        "host_runtime": "xv7_api_container",
        "repo_root": str(root),
        "latest_diagnosis_status": latest_diagnosis_status,
        "checks": checks,
        "first_blocker": first_blocker,
        "recommended_next_action": "X Kernel safe tool execution is ready." if status == "pass" else "Inspect failing X Kernel readiness checks.",
    }
    latest, stamped = _write_receipt("readiness", payload)
    stdout = (
        f"X Kernel Readiness: {status.upper()}\n"
        f"Runtime: xv7_api_container\n"
        f"Repo: {root}\n"
        f"Latest diagnosis status: {latest_diagnosis_status}\n"
        f"First blocker: {first_blocker}\n"
        f"Recommended next action: {payload['recommended_next_action']}\n"
        f"Proof: {latest}\n"
        f"Saved readiness receipt: {stamped}"
    )
    return {
        "status": "completed" if status == "pass" else "failed",
        "returncode": 0 if status == "pass" else 1,
        "stdout": stdout,
        "receipt_path": str(latest),
    }


def _run_state() -> dict[str, Any]:
    root = _repo_root()
    receipts = _receipt_root()
    latest_diagnose = _load_json(receipts / "latest_diagnose.json")
    latest_readiness = _load_json(receipts / "latest_readiness.json")
    payload = {
        "receipt_type": "x_kernel_state",
        "created_at": _utc_now(),
        "identity": "X / Xoduz",
        "owner": "Otis Duncan",
        "host_runtime": "xv7_api_container",
        "repo_root": str(root),
        "diagnosis_status": latest_diagnose.get("overall_status", "unknown"),
        "readiness_status": latest_readiness.get("readiness_status", "unknown"),
        "first_blocker": latest_readiness.get("first_blocker") or latest_diagnose.get("first_blocker", "unknown"),
        "recommended_next_action": latest_readiness.get("recommended_next_action") or latest_diagnose.get("recommended_next_action", "Review latest receipts."),
    }
    latest, _stamped = _write_receipt("state", payload)
    stdout = (
        "X State Snapshot\n"
        f"Identity: {payload['identity']}\n"
        f"Owner: {payload['owner']}\n"
        f"Runtime: {payload['host_runtime']}\n"
        f"Repo: {payload['repo_root']}\n"
        f"Diagnosis: {payload['diagnosis_status']}\n"
        f"Readiness: {payload['readiness_status']}\n"
        f"First blocker: {payload['first_blocker']}\n"
        f"Recommended next action: {payload['recommended_next_action']}\n"
        f"Proof: {latest}"
    )
    return {
        "status": "completed",
        "returncode": 0,
        "stdout": stdout,
        "receipt_path": str(latest),
    }


def _run_proof() -> dict[str, Any]:
    root = _repo_root()
    receipts_root = _receipt_root()
    receipts_root.mkdir(parents=True, exist_ok=True)
    receipts = sorted(receipts_root.glob("*.json"))
    lines = [
        "X Proof Ledger",
        "Runtime: xv7_api_container",
        f"Receipt directory: {receipts_root}",
        f"Receipt count: {len(receipts)}",
    ]
    lines.extend(f"- {path.name}" for path in receipts[-12:])
    payload = {
        "receipt_type": "x_kernel_proof",
        "created_at": _utc_now(),
        "host_runtime": "xv7_api_container",
        "repo_root": str(root),
        "receipt_directory": str(receipts_root),
        "receipt_count": len(receipts),
        "recent_receipts": [path.name for path in receipts[-12:]],
    }
    latest, _stamped = _write_receipt("proof", payload)
    return {
        "status": "completed",
        "returncode": 0,
        "stdout": "\n".join(lines),
        "receipt_path": str(latest),
    }


def run_x_kernel_tool(decision: dict[str, Any]) -> dict[str, Any]:
    """Run one safe X Kernel tool action from a kernel decision."""

    if not isinstance(decision, dict):
        return _rejected("decision_not_dict")

    intent = str(decision.get("intent") or "")
    route = str(decision.get("route") or "")
    risk = str(decision.get("risk") or "")

    if risk in FORBIDDEN_RISKS:
        return _rejected(f"risk_not_allowed:{risk}")
    if route != "tool":
        return _rejected(f"route_not_allowed:{route}")
    if intent not in ALLOWED_INTENTS:
        return _rejected(f"intent_not_allowed:{intent}")

    try:
        if intent == "diagnose":
            result = _run_diagnose()
        elif intent == "readiness":
            result = _run_readiness()
        elif intent == "state":
            result = _run_state()
        else:
            result = _run_proof()
    except Exception as exc:  # defensive API boundary: return receipt-shaped failure
        return {
            "executed": False,
            "allowed": True,
            "status": "error",
            "reason": str(exc),
            "intent": intent,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "executed": True,
        "allowed": True,
        "reason": "allowlisted_kernel_tool",
        "intent": intent,
        "stderr": "",
        **result,
        "stdout": _tail(result.get("stdout")),
    }


def _rejected(reason: str) -> dict[str, Any]:
    return {
        "executed": False,
        "allowed": False,
        "status": "rejected",
        "reason": reason,
        "intent": None,
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }


def render_tool_result(tool_result: dict[str, Any]) -> str:
    rendered = (
        "Tool execution:\n"
        f"Status: {tool_result.get('status') or 'unknown'}\n"
        f"Allowed: {tool_result.get('allowed')}\n"
        f"Executed: {tool_result.get('executed')}\n"
        f"Return code: {tool_result.get('returncode')}\n"
    )
    if tool_result.get("receipt_path"):
        rendered += f"Proof: {tool_result.get('receipt_path')}\n"
    rendered += "\nStdout:\n" + str(tool_result.get("stdout") or "none")
    if tool_result.get("stderr"):
        rendered += "\n\nStderr:\n" + str(tool_result.get("stderr"))
    return rendered.rstrip()


def apply_x_kernel_tool_result_to_session_state(session_state: SessionState) -> SessionState:
    """Attach safe tool output to the returned API SessionState."""

    decision = session_state.metadata.get("x_kernel_decision")
    if not isinstance(decision, dict):
        return session_state

    intent = str(decision.get("intent") or "")
    if intent not in ALLOWED_INTENTS:
        return session_state
    if not session_state.messages:
        return session_state

    last_message = session_state.messages[-1]
    if last_message.role != "assistant":
        return session_state
    if last_message.metadata.get("x_kernel_tool_result"):
        return session_state

    tool_result = run_x_kernel_tool(decision)
    next_content = f"{last_message.content.rstrip()}\n\n{render_tool_result(tool_result)}"
    next_metadata = dict(last_message.metadata)
    next_metadata["x_kernel_tool_result"] = tool_result

    messages = list(session_state.messages)
    messages[-1] = _copy_model(
        last_message,
        content=next_content,
        metadata=next_metadata,
    )

    updated_metadata = dict(session_state.metadata)
    updated_metadata["x_kernel_tool_result"] = tool_result
    updated_metadata["x_kernel_tool_runner"] = {
        "version": "v0",
        "mode": "allowlisted_read_only_container_native",
        "status": tool_result.get("status"),
    }
    return _copy_model(session_state, messages=messages, metadata=updated_metadata)
