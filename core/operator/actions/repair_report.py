from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.operator.actions.patch_report import operator_patch_report
from core.operator.actions.status_report import operator_status_report
from core.operator.actions.validation_report import operator_validation_report
from core.operator.schema import OperatorActionResult, OperatorSafety


def _approved(payload: dict[str, Any]) -> bool:
    approval = payload.get("approval")
    if isinstance(approval, bool):
        return approval
    if not isinstance(approval, dict):
        return False
    return approval.get("approved") is True or approval.get("status") == "approved"


def _result(
    *,
    action_id: str,
    started: datetime,
    repo_root: Path,
    status: str,
    stdout_summary: str,
    stderr_summary: str,
    data: dict[str, Any],
    allowed: bool = True,
    mutates_files: bool = False,
    requires_approval: bool = False,
) -> OperatorActionResult:
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_repair_report",
        mode="operator",
        status=status,  # type: ignore[arg-type]
        started_at=started,
        completed_at=datetime.now(UTC),
        command_or_operation="validation-driven repair cycle; no git commit or push",
        target=str(repo_root),
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        exit_code=0 if status == "success" else None,
        data=data
        | {
            "commit_created": False,
            "push_performed": False,
            "commit_push_waiting_for_approval": bool(data.get("changed_files")),
        },
        safety=OperatorSafety(
            read_only=False,
            mutates_files=mutates_files,
            mutates_git=False,
            mutates_runtime=False,
            requires_approval=requires_approval,
            allowed=allowed,
            denial_reason=None if allowed else stderr_summary,
        ),
        receipt_label=f"operator_repair_report {action_id}",
    )


def _validation_payload(request: dict[str, Any]) -> dict[str, Any]:
    commands = request.get("commands")
    if commands is not None and not isinstance(commands, list):
        commands = [str(commands)]
    return {
        "profile": str(request.get("profile") or "python-core"),
        "commands": [str(command) for command in commands]
        if commands is not None
        else None,
        "include_docker_if_modified": bool(
            request.get("include_docker_if_modified", True)
        ),
        "timeout_seconds": int(request.get("timeout_seconds", 300)),
    }


def _failed_command(validation: OperatorActionResult) -> str | None:
    command = validation.data.get("first_failure_command")
    return str(command) if command else None


def _patch_request_for_mode(
    patch_request: dict[str, Any],
    *,
    mode: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(patch_request)
    payload["mode"] = mode
    if "approval" not in payload and "approval" in request:
        payload["approval"] = request["approval"]
    return payload


def operator_repair_report(
    *,
    action_id: str,
    repo_root: Path,
    request: dict[str, Any],
) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    max_cycles = min(max(int(request.get("max_cycles", 1)), 1), 1)
    validation_request = _validation_payload(request)

    status_before = operator_status_report(
        action_id=f"{action_id}-status-before",
        repo_root=repo_root,
    )
    validation_before = operator_validation_report(
        action_id=f"{action_id}-validation-before",
        repo_root=repo_root,
        **validation_request,
    )

    patch_request = request.get("patch")
    base_data: dict[str, Any] = {
        "max_cycles": max_cycles,
        "status_before": status_before.structured_receipt(),
        "validation_before": validation_before.structured_receipt(),
        "validation_commands_run": validation_before.data.get("selected_commands", []),
        "first_failure_command": _failed_command(validation_before),
        "patch_required": False,
        "patch_preview": None,
        "patch_apply": None,
        "validation_after": None,
        "changed_files": [],
        "remaining_risks": [],
    }

    if validation_before.status == "denied":
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="denied",
            stdout_summary="validation request denied before repair",
            stderr_summary=validation_before.stderr_summary,
            data=base_data
            | {
                "remaining_risks": [
                    "Validation command/profile was denied by allowlist policy."
                ]
            },
            allowed=False,
        )

    if validation_before.data.get("passed") is True:
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="success",
            stdout_summary="validation passed; no repair patch applied",
            stderr_summary="",
            data=base_data | {"repair_fixed_failure": True},
        )

    first_failure_command = _failed_command(validation_before)
    if not isinstance(patch_request, dict):
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="failed",
            stdout_summary="validation failed; concrete patch required",
            stderr_summary=f"First validation failure: {first_failure_command}",
            data=base_data
            | {
                "patch_required": True,
                "remaining_risks": [
                    "A concrete approved patch is required before repair can mutate files."
                ],
            },
        )

    preview = operator_patch_report(
        action_id=f"{action_id}-patch-preview",
        repo_root=repo_root,
        request=_patch_request_for_mode(patch_request, mode="preview", request=request),
    )
    data_with_preview = base_data | {
        "patch_required": True,
        "patch_preview": preview.structured_receipt(),
    }
    if preview.status != "success":
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="denied",
            stdout_summary="patch preview blocked repair",
            stderr_summary=preview.stderr_summary,
            data=data_with_preview
            | {
                "remaining_risks": [
                    "Patch was blocked by safety policy before any mutation."
                ]
            },
            allowed=False,
            requires_approval=True,
        )

    if not _approved(request) and not _approved(patch_request):
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="denied",
            stdout_summary="patch apply denied before mutation",
            stderr_summary="Repair apply denied: explicit patch approval is required.",
            data=data_with_preview
            | {
                "remaining_risks": [
                    "Patch preview is available, but approval is required before apply."
                ]
            },
            allowed=False,
            requires_approval=True,
        )

    applied = operator_patch_report(
        action_id=f"{action_id}-patch-apply",
        repo_root=repo_root,
        request=_patch_request_for_mode(patch_request, mode="apply", request=request),
    )
    changed_files = list(applied.data.get("changed_files", []))
    data_with_apply = data_with_preview | {
        "patch_apply": applied.structured_receipt(),
        "changed_files": changed_files,
    }
    if applied.status != "success":
        return _result(
            action_id=action_id,
            started=started,
            repo_root=repo_root,
            status="denied",
            stdout_summary="patch apply blocked repair",
            stderr_summary=applied.stderr_summary,
            data=data_with_apply
            | {
                "remaining_risks": [
                    "Patch did not apply; validation was not rerun after repair."
                ]
            },
            allowed=False,
            mutates_files=False,
            requires_approval=True,
        )

    revalidation_commands = [first_failure_command] if first_failure_command else None
    validation_after = operator_validation_report(
        action_id=f"{action_id}-validation-after",
        repo_root=repo_root,
        profile=validation_request["profile"],
        commands=revalidation_commands,
        include_docker_if_modified=False,
        timeout_seconds=validation_request["timeout_seconds"],
    )
    fixed = validation_after.data.get("passed") is True
    return _result(
        action_id=action_id,
        started=started,
        repo_root=repo_root,
        status="success" if fixed else "failed",
        stdout_summary=(
            "repair validation passed after patch"
            if fixed
            else "repair validation still failing after patch"
        ),
        stderr_summary=""
        if fixed
        else f"First validation failure after repair: {_failed_command(validation_after)}",
        data=data_with_apply
        | {
            "validation_after": validation_after.structured_receipt(),
            "repair_fixed_failure": fixed,
            "validation_commands_rerun": validation_after.data.get(
                "selected_commands", []
            ),
            "remaining_risks": []
            if fixed
            else ["The first failed validation command still fails after repair."],
        },
        mutates_files=bool(changed_files),
        requires_approval=True,
    )
