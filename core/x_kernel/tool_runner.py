"""Safe X Kernel tool result helpers.

This module exposes only allowlisted self-status actions for the XV7/X message
route. It does not evaluate user-provided commands.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.runtime.schemas import SessionState

ALLOWED_INTENTS = {"diagnose", "readiness", "state", "proof"}
FORBIDDEN_RISKS = {"developer_write", "system_control", "network_control"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _capture_print(fn: Any, *args: Any, **kwargs: Any) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn(*args, **kwargs)
    return buffer.getvalue().rstrip()


def _run_diagnose() -> dict[str, Any]:
    from scripts import xv7_x

    root = xv7_x.repo_root()
    receipt = xv7_x.run_diagnose(root)
    saved = xv7_x.save_receipt(root, receipt, "diagnose")
    proof = root / xv7_x.RECEIPT_DIR / "latest_diagnose.json"
    stdout = _capture_print(xv7_x.print_diagnosis, receipt, proof)
    stdout += f"\nSaved diagnosis receipt: {saved}"
    return {
        "status": "completed",
        "returncode": 0,
        "stdout": stdout,
        "receipt_path": str(proof),
    }


def _run_readiness() -> dict[str, Any]:
    from scripts import xv7_x

    root = xv7_x.repo_root()
    receipt = xv7_x.run_readiness(root)
    saved = xv7_x.save_receipt(root, receipt, "readiness")
    proof = root / xv7_x.RECEIPT_DIR / "latest_readiness.json"
    stdout = _capture_print(xv7_x.print_readiness, receipt, proof)
    stdout += f"\nSaved readiness receipt: {saved}"
    return {
        "status": "completed",
        "returncode": 0,
        "stdout": stdout,
        "receipt_path": str(proof),
    }


def _run_state() -> dict[str, Any]:
    from scripts import xv7_x

    root = xv7_x.repo_root()
    receipts = root / xv7_x.RECEIPT_DIR
    latest_diagnose = _load_json(receipts / "latest_diagnose.json")
    latest_readiness = _load_json(receipts / "latest_readiness.json")
    payload = {
        "receipt_type": "x_kernel_state",
        "created_at": _utc_now(),
        "identity": "X / Xoduz",
        "owner": "Otis Duncan",
        "repo_root": str(root),
        "diagnosis_status": latest_diagnose.get("overall_status", "unknown"),
        "readiness_status": latest_readiness.get("readiness_status", "unknown"),
        "first_blocker": latest_readiness.get("first_blocker")
        or (latest_diagnose.get("first_blocker") or {}).get("blocker_id", "unknown"),
        "recommended_next_action": latest_readiness.get("recommended_next_action")
        or latest_diagnose.get("recommended_next_action", "Review latest receipts."),
    }
    latest = receipts / "latest_state.json"
    _save_json(latest, payload)
    stamped = receipts / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_state.json"
    _save_json(stamped, payload)
    stdout = (
        "X State Snapshot\n"
        f"Identity: {payload['identity']}\n"
        f"Owner: {payload['owner']}\n"
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
    from scripts import xv7_x

    root = xv7_x.repo_root()
    receipts = sorted((root / xv7_x.RECEIPT_DIR).glob("*.json"))
    lines = [
        "X Proof Ledger",
        f"Receipt directory: {root / xv7_x.RECEIPT_DIR}",
        f"Receipt count: {len(receipts)}",
    ]
    lines.extend(f"- {path.name}" for path in receipts[-12:])
    return {
        "status": "completed",
        "returncode": 0,
        "stdout": "\n".join(lines),
        "receipt_path": str(root / xv7_x.RECEIPT_DIR),
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
        "mode": "allowlisted_read_only_direct_functions",
        "status": tool_result.get("status"),
    }
    return _copy_model(session_state, messages=messages, metadata=updated_metadata)
