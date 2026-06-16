from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from core.operator.operator_intent import FIRST_CLASS_SLASH_COMMANDS
from core.operator.schema import OperatorActionResult, OperatorSafety


def pending_key() -> str:
    return "operator_pending_action"


def get_pending_action(session_metadata: dict[str, Any]) -> dict[str, Any] | None:
    pending = session_metadata.get(pending_key())
    if not isinstance(pending, dict):
        return None
    return pending


def clear_pending_action(session_metadata: dict[str, Any]) -> None:
    session_metadata.pop(pending_key(), None)


def stage_slash_command(
    *,
    command_text: str,
    operator_mode: bool,
    session_metadata: dict[str, Any],
    repo_root: Path,
    pending_ttl_seconds: int,
    slash_commands: dict[str, Any],
    parse_slash_command: Callable[[str], tuple[str, list[str]]],
    build_result: Callable[..., OperatorActionResult],
    build_answer: Callable[[str, OperatorActionResult], str],
    try_handle_chat: Callable[..., Any],
    build_task_plan_result: Callable[[str, list[str]], OperatorActionResult],
    read_only_scan_result: Callable[[str, list[str]], OperatorActionResult],
    validate_apply_patch_stage_payload: Callable[
        [str, list[str]], OperatorActionResult | None
    ],
    next_action_id: Callable[[], str],
) -> dict[str, Any]:
    normalized = command_text.strip()
    slash, args = parse_slash_command(normalized)
    spec = slash_commands.get(slash)
    if spec is None:
        result = build_result(
            action_name="unknown_slash_command",
            status="failed",
            command_preview=normalized,
            target=str(repo_root),
            stderr=f"Unknown slash command: {slash}",
        )
        return {
            "answer": f"Unknown slash command: {slash}",
            "result": result,
            "pending_action": None,
            "executed": False,
        }

    if slash == "/build-task" and not operator_mode:
        result = build_result(
            action_name="build_task",
            status="denied",
            mode_override="operator",
            command_preview=normalized,
            target=str(repo_root),
            stderr="/build-task requires Operator Mode.",
        )
        return {
            "answer": "/build-task requires Operator Mode. No files were changed. No tests were run. No commit or push occurred.",
            "result": result,
            "pending_action": None,
            "executed": False,
        }

    if slash in FIRST_CLASS_SLASH_COMMANDS:
        execution = try_handle_chat(
            command_text,
            session_metadata=session_metadata,
            operator_mode_enabled=True,
        )
        if execution is None:
            result = build_result(
                action_name=slash.strip("/"),
                status="failed",
                command_preview=normalized,
                target=str(repo_root),
                stderr="Command was recognized but could not be routed.",
                mutates_files=True,
            )
            return {
                "answer": build_answer(result.action_name, result),
                "result": result,
                "pending_action": None,
                "executed": True,
            }
        pending_action = None
        executed = execution.result.status != "pending"
        if execution.result.status == "pending":
            pending_action = {
                "action_id": execution.result.action_id,
                "command_name": slash.strip("/"),
                "target": execution.result.target,
                "command_preview": normalized,
                "status": "pending",
                "requires_confirmation": True,
            }
        return {
            "answer": execution.answer,
            "result": execution.result,
            "pending_action": pending_action,
            "executed": executed,
        }

    if spec.mode != "read_only" and not operator_mode:
        result = build_result(
            action_name=slash.strip("/"),
            status="denied",
            command_preview=normalized,
            target=str(repo_root),
            stderr="Operator Mode is OFF. Mutation slash commands are disabled.",
            mutates_files=True,
        )
        return {
            "answer": "Operator Mode is OFF. This mutation command is blocked until Operator Mode is enabled.",
            "result": result,
            "pending_action": None,
            "executed": False,
        }

    if slash == "/build-task":
        result = build_task_plan_result(normalized, args)
        return {
            "answer": build_answer("build_task", result),
            "result": result,
            "pending_action": None,
            "executed": True,
        }

    if spec.mode == "read_only":
        result = read_only_scan_result(slash, args)
        return {
            "answer": build_answer(result.action_name, result),
            "result": result,
            "pending_action": None,
            "executed": True,
        }

    if slash == "/apply-patch":
        invalid = validate_apply_patch_stage_payload(normalized, args)
        if invalid is not None:
            return {
                "answer": build_answer(invalid.action_name, invalid),
                "result": invalid,
                "pending_action": None,
                "executed": True,
            }

    action_id = next_action_id()
    now = datetime.now(UTC)
    target = args[0] if args else "(no target)"
    confirmation_phrase = None
    if spec.requires_typed_confirmation and spec.confirmation_phrase:
        confirmation_phrase = spec.confirmation_phrase.replace("{target}", target)

    pending_action = {
        "action_id": action_id,
        "command_name": slash.strip("/"),
        "category": spec.category,
        "target": target,
        "arguments": args,
        "mode": "operator",
        "risk_level": spec.risk_level,
        "command_preview": normalized,
        "human_summary": f"Prepare {slash} on {target}",
        "reversible": spec.reversible,
        "requires_confirmation": True,
        "requires_typed_confirmation": spec.requires_typed_confirmation,
        "confirmation_phrase": confirmation_phrase,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": datetime.fromtimestamp(
            now.timestamp() + pending_ttl_seconds, tz=UTC
        ).isoformat(),
        "implemented": spec.implemented,
    }
    session_metadata[pending_key()] = pending_action

    result = OperatorActionResult(
        action_id=action_id,
        action_name=slash.strip("/"),
        mode="high_risk" if spec.risk_level == "high" else "operator",
        status="pending",
        started_at=now,
        completed_at=now,
        command_or_operation=normalized,
        target=target,
        stdout_summary="pending confirmation",
        stderr_summary="",
        exit_code=None,
        data={
            "risk_level": spec.risk_level,
            "reversible": spec.reversible,
            "requires_typed_confirmation": spec.requires_typed_confirmation,
            "confirmation_phrase": confirmation_phrase,
            "command_preview": normalized,
            "status": "pending_confirmation",
        },
        safety=OperatorSafety(
            allowed=True,
            read_only=False,
            mutates_files=True,
            requires_approval=True,
        ),
        receipt_label=f"{slash.strip('/')} {action_id}",
    )
    answer = "I'm ready to perform this operator action, but I need confirmation first."
    return {
        "answer": answer,
        "result": result,
        "pending_action": pending_action,
        "executed": False,
    }
