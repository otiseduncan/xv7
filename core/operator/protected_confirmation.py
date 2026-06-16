from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from core.operator.schema import OperatorActionResult, OperatorSafety


def confirm_pending_action(
    *,
    pending_action: dict[str, Any] | None,
    typed_confirmation: str | None,
    repo_root: Path,
    slash_commands: dict[str, Any],
    build_result: Callable[..., OperatorActionResult],
    execute_mutation: Callable[[str, list[str]], OperatorActionResult],
    build_answer: Callable[[str, OperatorActionResult], str],
) -> dict[str, Any]:
    if not pending_action:
        result = build_result(
            action_name="operator_confirm",
            status="failed",
            command_preview="confirm pending operator action",
            target=str(repo_root),
            stderr="No pending operator action to confirm.",
        )
        return {
            "answer": "No pending operator action to confirm.",
            "result": result,
        }

    expires_at = str(pending_action.get("expires_at", ""))
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.now(UTC) > expiry:
                result = build_result(
                    action_name=str(
                        pending_action.get("command_name", "operator_action")
                    ),
                    status="failed",
                    command_preview=str(pending_action.get("command_preview", "")),
                    target=str(pending_action.get("target", str(repo_root))),
                    stderr="Pending action expired.",
                )
                return {
                    "answer": "Pending action expired. Stage the command again.",
                    "result": result,
                }
        except Exception:
            pass

    if pending_action.get("requires_typed_confirmation"):
        expected = str(pending_action.get("confirmation_phrase") or "").strip()
        provided = str(typed_confirmation or "").strip()
        if not expected or provided != expected:
            result = build_result(
                action_name=str(pending_action.get("command_name", "operator_action")),
                status="failed",
                mode_override="high_risk",
                command_preview=str(pending_action.get("command_preview", "")),
                target=str(pending_action.get("target", str(repo_root))),
                stderr="Typed confirmation did not match.",
                data={"typed_confirmation": "mismatch"},
            )
            return {
                "answer": "Typed confirmation did not match. Action is still blocked.",
                "result": result,
            }

    slash = "/" + str(pending_action.get("command_name", "")).lstrip("/")
    args = pending_action.get("arguments", [])
    spec = slash_commands.get(slash)
    if spec is None:
        result = build_result(
            action_name=str(pending_action.get("command_name", "operator_action")),
            status="failed",
            command_preview=str(pending_action.get("command_preview", "")),
            target=str(pending_action.get("target", str(repo_root))),
            stderr="Pending command no longer exists.",
        )
        return {"answer": "Pending command no longer exists.", "result": result}

    if not spec.implemented:
        result = build_result(
            action_name=str(pending_action.get("command_name", "operator_action")),
            status="not_implemented",
            mode_override="high_risk"
            if bool(pending_action.get("requires_typed_confirmation"))
            else "operator",
            command_preview=str(pending_action.get("command_preview", "")),
            target=str(pending_action.get("target", str(repo_root))),
            stderr="Action not implemented yet.",
            data={"typed_confirmation": "matched"}
            if bool(pending_action.get("requires_typed_confirmation"))
            else {},
            mutates_files=True,
        )
        return {"answer": "Action not implemented yet.", "result": result}

    result = execute_mutation(slash, list(args) if isinstance(args, list) else [])
    if result.status == "success":
        answer = f"Operator action {result.action_name} executed successfully."
    else:
        answer = build_answer(result.action_name, result)
    return {"answer": answer, "result": result}


def cancel_pending_action(
    *,
    pending_action: dict[str, Any] | None,
    repo_root: Path,
    build_result: Callable[..., OperatorActionResult],
    next_action_id: Callable[[], str],
) -> dict[str, Any]:
    if not pending_action:
        result = build_result(
            action_name="operator_cancel",
            status="failed",
            command_preview="cancel pending operator action",
            target=str(repo_root),
            stderr="No pending operator action to cancel.",
        )
        return {"answer": "No pending operator action to cancel.", "result": result}

    result = OperatorActionResult(
        action_id=str(pending_action.get("action_id", next_action_id())),
        action_name=str(pending_action.get("command_name", "operator_action")),
        mode="high_risk"
        if bool(pending_action.get("requires_typed_confirmation"))
        else "operator",
        status="cancelled",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        command_or_operation=str(pending_action.get("command_preview", "cancel")),
        target=str(pending_action.get("target", str(repo_root))),
        stdout_summary="pending action cancelled",
        stderr_summary="",
        exit_code=None,
        data={"status": "cancelled"},
        safety=OperatorSafety(
            allowed=True,
            read_only=False,
            requires_approval=True,
            mutates_files=True,
        ),
        receipt_label=f"{pending_action.get('command_name', 'operator_action')} {pending_action.get('action_id', 'n/a')}",
    )
    return {
        "answer": "Pending operator action was cancelled.",
        "result": result,
    }
