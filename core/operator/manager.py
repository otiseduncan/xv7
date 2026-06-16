from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.brain.sandbox_writer import SandboxWriteManager
from core.operator.history import get_history, latest_action, latest_action_by_name
from core.operator.operator_chat_router_service import OperatorChatRouterService
from core.operator.operator_intent import (
    FIRST_CLASS_SLASH_COMMANDS,
    dedup_paths,
    extract_json_object,
    extract_repo_name_from_prompt,
    extract_windows_paths,
    is_commit_proposal_request,
    is_commit_push_operator_request,
    is_first_class_operator_request,
    is_github_proof_project_request,
    is_natural_repair_request,
    is_natural_validation_request,
    is_non_mutation_writing_request,
    looks_like_natural_language_request,
    missing_project_path_message,
    normalize_text,
    slugify_repo_name,
    strip_operator_mode_prefix,
    translate_first_class_slash,
)
from core.operator.operator_paths import (
    extract_read_target,
    path_allowed,
    resolve_target_path,
)
from core.operator.operator_receipts import build_operator_answer
from core.operator.protected_confirmation import (
    cancel_pending_action as service_cancel_pending_action,
    confirm_pending_action as service_confirm_pending_action,
)
from core.operator.staged_action_service import (
    clear_pending_action as service_clear_pending_action,
    get_pending_action as service_get_pending_action,
    pending_key as service_pending_key,
    stage_slash_command as service_stage_slash_command,
)
from core.operator.operator_types import OperatorExecution
from core.operator.registry import build_operator_registry, run_action
from core.operator.schema import (
    OperatorActionResult,
    OperatorMode,
    OperatorSafety,
    OperatorStatus,
)
from core.operator.slash_commands import (
    SlashCommandSpec,
    build_slash_command_registry,
)


class OperatorManager:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self._counter = 0
        self.registry = build_operator_registry()
        self.pending_ttl_seconds = 300
        self.slash_commands: dict[str, SlashCommandSpec] = (
            build_slash_command_registry()
        )

    def list_slash_commands(self, *, operator_mode: bool) -> list[dict[str, Any]]:
        commands: list[dict[str, Any]] = []
        for slash, spec in sorted(
            self.slash_commands.items(), key=lambda item: item[0]
        ):
            first_class = slash in FIRST_CLASS_SLASH_COMMANDS
            enabled = spec.mode == "read_only" or operator_mode or first_class
            visible = spec.mode == "read_only" or operator_mode or first_class
            commands.append(
                {
                    "slash": slash,
                    "category": spec.category,
                    "risk_level": spec.risk_level,
                    "mode": spec.mode,
                    "visible": visible,
                    "enabled": enabled,
                    "requires_typed_confirmation": spec.requires_typed_confirmation,
                    "confirmation_phrase": spec.confirmation_phrase,
                    "implemented": spec.implemented,
                }
            )
        return commands

    @staticmethod
    def _pending_key() -> str:
        return service_pending_key()

    def get_pending_action(
        self, session_metadata: dict[str, Any]
    ) -> dict[str, Any] | None:
        return service_get_pending_action(session_metadata)

    def clear_pending_action(self, session_metadata: dict[str, Any]) -> None:
        service_clear_pending_action(session_metadata)

    def _resolve_target_path(self, raw: str) -> Path:
        return resolve_target_path(raw, self.repo_root)

    def _path_allowed(self, path: Path) -> bool:
        return path_allowed(path, self.repo_root)

    def _parse_slash_command(self, command_text: str) -> tuple[str, list[str]]:
        if not command_text.strip().startswith("/"):
            raise ValueError("Slash command must start with '/'.")
        parts = shlex.split(command_text, posix=False)
        if not parts:
            raise ValueError("Command is empty.")
        return parts[0].lower(), parts[1:]

    @staticmethod
    def _looks_like_natural_language_request(text: str) -> bool:
        return looks_like_natural_language_request(text)

    def _validate_apply_patch_stage_payload(
        self, command_preview: str, args: list[str]
    ) -> OperatorActionResult | None:
        payload_text = " ".join(args).strip()
        invalid_payload_message = (
            "Invalid patch payload. /apply-patch requires a valid approved patch payload, "
            "not a natural-language build request."
        )

        if not payload_text:
            return self._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            if self._looks_like_natural_language_request(payload_text):
                return self._build_result(
                    action_name="apply_patch",
                    status="failed",
                    command_preview=command_preview,
                    target=str(self.repo_root),
                    stderr=invalid_payload_message,
                    mutates_files=True,
                    requires_approval=True,
                )
            return self._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        if not isinstance(payload, dict):
            return self._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        has_change_shape = isinstance(payload.get("changes"), list) or isinstance(
            payload.get("path"), str
        )
        if not has_change_shape:
            return self._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        return None

    def _build_result(
        self,
        *,
        action_name: str,
        status: OperatorStatus,
        mode_override: OperatorMode | None = None,
        command_preview: str,
        target: str,
        stdout: str = "",
        stderr: str = "",
        data: dict[str, Any] | None = None,
        mutates_files: bool = False,
        mutates_runtime: bool = False,
        mutates_git: bool = False,
        requires_approval: bool = False,
    ) -> OperatorActionResult:
        now = datetime.now(UTC)
        mode: OperatorMode = mode_override or (
            "operator"
            if (mutates_files or mutates_runtime or mutates_git)
            else "read_only"
        )
        safety = OperatorSafety(
            allowed=status != "denied",
            read_only=not (mutates_files or mutates_runtime or mutates_git),
            mutates_files=mutates_files,
            mutates_runtime=mutates_runtime,
            mutates_git=mutates_git,
            requires_approval=requires_approval,
        )
        return OperatorActionResult(
            action_id=self._next_action_id(),
            action_name=action_name,
            mode=mode,
            status=status,
            started_at=now,
            completed_at=now,
            command_or_operation=command_preview,
            target=target,
            stdout_summary=stdout,
            stderr_summary=stderr,
            exit_code=0 if status == "success" else None,
            data=data or {},
            safety=safety,
            receipt_label=f"{action_name} {datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        )

    def _read_only_scan_result(
        self, slash: str, args: list[str]
    ) -> OperatorActionResult:
        if slash == "/scan-repo":
            return run_action(
                "repo_status",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-system":
            return run_action(
                "scan_system",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-cpu":
            return run_action(
                "scan_cpu", action_id=self._next_action_id(), repo_root=self.repo_root
            )
        if slash == "/scan-gpu":
            return run_action(
                "scan_gpu", action_id=self._next_action_id(), repo_root=self.repo_root
            )
        if slash in {"/scan-disk", "/list-disk", "/list-disks", "/list-drives"}:
            return run_action(
                "scan_disk", action_id=self._next_action_id(), repo_root=self.repo_root
            )
        if slash == "/scan-network":
            return run_action(
                "scan_network",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-ports":
            return run_action(
                "scan_ports", action_id=self._next_action_id(), repo_root=self.repo_root
            )
        if slash == "/scan-processes":
            return run_action(
                "scan_processes",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-services":
            return run_action(
                "scan_services",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-docker":
            return run_action(
                "scan_docker",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/scan-vscode":
            return run_action(
                "scan_vscode",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/list-files":
            return run_action(
                "list_project_files",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
            )
        if slash == "/read-file":
            if not args:
                return self._build_result(
                    action_name="read_file",
                    status="failed",
                    command_preview="read project file",
                    target=str(self.repo_root),
                    stderr="Missing target path. Usage: /read-file <path>",
                )
            return run_action(
                "read_project_file",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
                target=args[0],
            )
        if slash == "/search-files":
            if not args:
                return self._build_result(
                    action_name="search_files",
                    status="failed",
                    command_preview="search project files",
                    target=str(self.repo_root),
                    stderr="Missing search query. Usage: /search-files <text>",
                )
            query = args[0].lower()
            files = sorted(
                str(path.relative_to(self.repo_root)).replace("\\", "/")
                for path in self.repo_root.rglob("*")
                if path.is_file()
                and query in str(path).lower()
                and ".git" not in path.parts
            )[:60]
            return self._build_result(
                action_name="search_files",
                status="success",
                command_preview=f"search files for '{query}'",
                target=str(self.repo_root),
                stdout=f"matches={len(files)}",
                data={"matches": files},
            )
        if slash == "/run-tests":
            target: str | None = None
            if args:
                requested = " ".join(args).strip()
                if requested.startswith(("tests/", "tests\\")):
                    target = json.dumps(
                        {
                            "preset": "single_pytest",
                            "test_target": requested,
                        }
                    )
                else:
                    target = requested
            try:
                return run_action(
                    "test_runner",
                    action_id=self._next_action_id(),
                    repo_root=self.repo_root,
                    target=target,
                )
            except ValueError as exc:
                return self._build_result(
                    action_name="run_tests",
                    status="failed",
                    command_preview="run allowlisted tests",
                    target=str(self.repo_root),
                    stderr=str(exc),
                )
        return self._build_result(
            action_name=slash.strip("/"),
            status="failed",
            command_preview=slash,
            target=str(self.repo_root),
            stderr="Action not implemented yet.",
        )

    def _build_task_plan_result(
        self, command_preview: str, args: list[str]
    ) -> OperatorActionResult:
        goal = " ".join(args).strip()
        if not goal:
            return self._build_result(
                action_name="build_task",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr="Missing build task request. Usage: /build-task <natural-language request>",
            )

        try:
            return run_action(
                "patch_plan",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
                target=goal,
            )
        except ValueError as exc:
            return self._build_result(
                action_name="build_task",
                status="failed",
                command_preview=command_preview,
                target=str(self.repo_root),
                stderr=str(exc),
            )

    def _execute_mutation(self, slash: str, args: list[str]) -> OperatorActionResult:
        if slash == "/delete-file":
            if not args:
                return self._build_result(
                    action_name="delete_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Missing path argument.",
                    mutates_files=True,
                )
            target = self._resolve_target_path(args[0])
            if not self._path_allowed(target):
                return self._build_result(
                    action_name="delete_file",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            if not target.exists() or not target.is_file():
                return self._build_result(
                    action_name="delete_file",
                    status="failed",
                    command_preview=slash,
                    target=str(target),
                    stderr="File not found.",
                    mutates_files=True,
                )
            target.unlink()
            return self._build_result(
                action_name="delete_file",
                status="success",
                command_preview=f'Remove-Item "{target}"',
                target=str(target),
                stdout="file deleted",
                mutates_files=True,
            )

        if slash == "/rename-file":
            if len(args) < 2:
                return self._build_result(
                    action_name="rename_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Usage: /rename-file <old> <new>",
                    mutates_files=True,
                )
            src = self._resolve_target_path(args[0])
            dst = self._resolve_target_path(args[1])
            if not self._path_allowed(src) or not self._path_allowed(dst):
                return self._build_result(
                    action_name="rename_file",
                    status="denied",
                    command_preview=slash,
                    target=str(src),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            if not src.exists() or not src.is_file():
                return self._build_result(
                    action_name="rename_file",
                    status="failed",
                    command_preview=slash,
                    target=str(src),
                    stderr="Source file not found.",
                    mutates_files=True,
                )
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return self._build_result(
                action_name="rename_file",
                status="success",
                command_preview=f'Rename-Item "{src}" "{dst.name}"',
                target=str(dst),
                stdout="file renamed",
                mutates_files=True,
            )

        if slash == "/create-folder":
            if not args:
                return self._build_result(
                    action_name="create_folder",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Missing folder path.",
                    mutates_files=True,
                )
            target = self._resolve_target_path(args[0])
            if not self._path_allowed(target):
                return self._build_result(
                    action_name="create_folder",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            target.mkdir(parents=True, exist_ok=True)
            return self._build_result(
                action_name="create_folder",
                status="success",
                command_preview=f'New-Item -ItemType Directory -Path "{target}"',
                target=str(target),
                stdout="folder created",
                mutates_files=True,
            )

        if slash == "/write-file":
            if len(args) < 2:
                return self._build_result(
                    action_name="write_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Usage: /write-file <path> <content>",
                    mutates_files=True,
                )
            target = self._resolve_target_path(args[0])
            content = " ".join(args[1:])
            if not self._path_allowed(target):
                return self._build_result(
                    action_name="write_file",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return self._build_result(
                action_name="write_file",
                status="success",
                command_preview=f'Set-Content "{target}"',
                target=str(target),
                stdout=f"wrote {len(content)} chars",
                mutates_files=True,
            )

        if slash == "/append-file":
            if len(args) < 2:
                return self._build_result(
                    action_name="append_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Usage: /append-file <path> <content>",
                    mutates_files=True,
                )
            target = self._resolve_target_path(args[0])
            content = " ".join(args[1:])
            if not self._path_allowed(target):
                return self._build_result(
                    action_name="append_file",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
            return self._build_result(
                action_name="append_file",
                status="success",
                command_preview=f'Add-Content "{target}"',
                target=str(target),
                stdout=f"appended {len(content)} chars",
                mutates_files=True,
            )

        if slash == "/restart-container":
            if not args:
                return self._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=slash,
                    target=str(self.repo_root),
                    stderr="Usage: /restart-container <name>",
                    mutates_runtime=True,
                )
            container_name = args[0]
            docker_cli = shutil.which("docker")
            if not docker_cli:
                return self._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=slash,
                    target=container_name,
                    stderr="Docker CLI unavailable.",
                    mutates_runtime=True,
                )
            proc = subprocess.run(
                ["docker", "compose", "restart", container_name],
                cwd=str(self.repo_root),
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                return self._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=f"docker compose restart {container_name}",
                    target=container_name,
                    stderr=proc.stderr[:400] or "restart failed",
                    mutates_runtime=True,
                )
            return self._build_result(
                action_name="restart_container",
                status="success",
                command_preview=f"docker compose restart {container_name}",
                target=container_name,
                stdout="container restarted",
                mutates_runtime=True,
            )

        if slash == "/apply-patch":
            patch_payload = " ".join(args).strip()
            try:
                return run_action(
                    "apply_approved_patch",
                    action_id=self._next_action_id(),
                    repo_root=self.repo_root,
                    target=patch_payload,
                )
            except ValueError as exc:
                return self._build_result(
                    action_name="apply_patch",
                    status="failed",
                    command_preview="approval-gated patch apply",
                    target=str(self.repo_root),
                    stderr=str(exc),
                    mutates_files=True,
                    requires_approval=True,
                )

        return self._build_result(
            action_name=slash.strip("/"),
            status="failed",
            command_preview=slash,
            target=str(self.repo_root),
            stderr="Action not implemented yet.",
            mutates_files=True,
        )

    def stage_slash_command(
        self,
        command_text: str,
        *,
        operator_mode: bool,
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return service_stage_slash_command(
            command_text=command_text,
            operator_mode=operator_mode,
            session_metadata=session_metadata,
            repo_root=self.repo_root,
            pending_ttl_seconds=self.pending_ttl_seconds,
            slash_commands=self.slash_commands,
            parse_slash_command=self._parse_slash_command,
            build_result=self._build_result,
            build_answer=self._build_answer,
            try_handle_chat=self.try_handle_chat,
            build_task_plan_result=self._build_task_plan_result,
            read_only_scan_result=self._read_only_scan_result,
            validate_apply_patch_stage_payload=self._validate_apply_patch_stage_payload,
            next_action_id=self._next_action_id,
        )

    def confirm_pending_action(
        self,
        pending_action: dict[str, Any] | None,
        *,
        typed_confirmation: str | None,
    ) -> dict[str, Any]:
        return service_confirm_pending_action(
            pending_action=pending_action,
            typed_confirmation=typed_confirmation,
            repo_root=self.repo_root,
            slash_commands=self.slash_commands,
            build_result=self._build_result,
            execute_mutation=self._execute_mutation,
            build_answer=self._build_answer,
        )

    def cancel_pending_action(
        self, pending_action: dict[str, Any] | None
    ) -> dict[str, Any]:
        return service_cancel_pending_action(
            pending_action=pending_action,
            repo_root=self.repo_root,
            build_result=self._build_result,
            next_action_id=self._next_action_id,
        )

    def _next_action_id(self) -> str:
        self._counter += 1
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return f"OP-{stamp}-{self._counter:04d}"

    def _run_action(self, action_name: str, **kwargs: Any) -> OperatorActionResult:
        return run_action(action_name, **kwargs)

    @staticmethod
    def _normalize(text: str) -> str:
        return normalize_text(text)

    def _denied_result(self, question: str, reason: str) -> OperatorActionResult:
        now = datetime.now(UTC)
        action_id = self._next_action_id()
        return OperatorActionResult(
            action_id=action_id,
            action_name="read_only_guard",
            status="denied",
            started_at=now,
            completed_at=now,
            command_or_operation="policy deny mutation request",
            target=str(self.repo_root),
            stdout_summary="",
            stderr_summary=reason,
            exit_code=None,
            data={"question": question},
            safety=OperatorSafety(allowed=False, denial_reason=reason),
            receipt_label=f"read_only_guard {action_id}",
        )

    def _extract_read_target(self, question: str) -> str:
        return extract_read_target(question)

    def _history_lookup_result(self) -> OperatorActionResult:
        now = datetime.now(UTC)
        action_id = self._next_action_id()
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_history_lookup",
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="read-only operator action history lookup",
            target=str(self.repo_root),
            stdout_summary="history lookup",
            stderr_summary="",
            exit_code=None,
            data={},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"operator_history_lookup {action_id}",
        )

    def _history_answer(
        self, normalized: str, session_metadata: dict[str, Any]
    ) -> OperatorExecution | None:
        if normalized in {"did you check the repo?", "did you check the repo"}:
            history = get_history(session_metadata)
            if not history:
                # Preserve legacy behavior: allow answer-contract path until any operator action exists.
                return None
            last_repo = latest_action_by_name(
                session_metadata, "operator_status_report"
            ) or latest_action_by_name(session_metadata, "repo_status")
            if last_repo is None:
                answer = "No live repo check has run in this session."
            else:
                status = str(last_repo.get("status", "unknown"))
                if status == "success":
                    answer = "Yes. I successfully checked the repo in this session."
                elif status == "failed":
                    answer = (
                        "I attempted a repo check, but it failed. "
                        "The failed operator receipt is available."
                    )
                else:
                    answer = "I attempted a repo check, but it did not succeed."
            return OperatorExecution(
                result=self._history_lookup_result(),
                answer=answer,
                record_history=False,
            )

        if normalized in {"what did you just check?", "what did you just check"}:
            latest = latest_action(session_metadata)
            if latest is None:
                answer = "No operator actions have run in this session yet."
            else:
                answer = (
                    "Latest operator action: "
                    f"{latest.get('action_name', 'unknown')} "
                    f"({latest.get('status', 'unknown')}) on {latest.get('target', 'unknown')}."
                )
            return OperatorExecution(
                result=self._history_lookup_result(),
                answer=answer,
                record_history=False,
            )

        if normalized in {
            "show the last operator receipt.",
            "show the last operator receipt",
        }:
            latest = latest_action(session_metadata)
            if latest is None:
                answer = "No operator receipt is available yet for this session."
            else:
                answer = (
                    "Last operator receipt summary: "
                    f"{latest.get('receipt_label', latest.get('action_name', 'unknown'))}; "
                    f"status={latest.get('status', 'unknown')}; "
                    f"target={latest.get('target', 'unknown')}."
                )
            return OperatorExecution(
                result=self._history_lookup_result(),
                answer=answer,
                record_history=False,
            )

        if normalized in {
            "what operator actions have run?",
            "what operator actions have run",
        }:
            history = get_history(session_metadata)
            if not history:
                answer = "No operator actions have run in this session yet."
            else:
                recent = history[-5:]
                lines = ["Recent operator actions:"]
                for item in recent:
                    lines.append(
                        f"- {item.get('action_name', 'unknown')} {item.get('status', 'unknown')} "
                        f"on {item.get('target', 'unknown')} ({item.get('action_id', 'n/a')})"
                    )
                answer = "\n".join(lines)
            return OperatorExecution(
                result=self._history_lookup_result(),
                answer=answer,
                record_history=False,
            )

        return None

    @staticmethod
    def _is_non_mutation_writing_request(normalized: str) -> bool:
        return is_non_mutation_writing_request(normalized)

    @staticmethod
    def _is_commit_proposal_request(normalized: str) -> bool:
        return is_commit_proposal_request(normalized)

    @staticmethod
    def _is_commit_push_operator_request(normalized: str) -> bool:
        return is_commit_push_operator_request(normalized)

    @staticmethod
    def _strip_operator_mode_prefix(normalized: str) -> str:
        return strip_operator_mode_prefix(normalized)

    @staticmethod
    def _extract_windows_paths(text: str) -> list[str]:
        return extract_windows_paths(text)

    @classmethod
    def _is_first_class_operator_request(cls, normalized: str) -> bool:
        return is_first_class_operator_request(normalized)

    def is_first_class_operator_prompt(self, question: str) -> bool:
        normalized = self._normalize(self._translate_first_class_slash(question))
        return self._is_first_class_operator_request(normalized)

    @staticmethod
    def _dedup_paths(paths: list[str]) -> list[str]:
        return dedup_paths(paths)

    @classmethod
    def _candidate_project_paths(cls, session_metadata: dict[str, Any]) -> list[str]:
        def _normalized_candidate_path(value: str) -> str | None:
            raw = str(value or "").strip().strip("\"'")
            if not raw:
                return None

            normalized = raw.replace("\\", "/")
            generated_match = re.search(
                r"(?:^|/)generated-sites/([^/]+)",
                normalized,
                flags=re.IGNORECASE,
            )
            if generated_match:
                slug = generated_match.group(1).strip("/\\ ")
                if slug:
                    return str((SandboxWriteManager.sandbox_root() / slug).resolve())

            if re.match(r"^[A-Za-z]:[\\/]", raw):
                candidate = Path(raw)
                if candidate.suffix:
                    return str(candidate.parent)
                return raw

            if raw.startswith("/"):
                candidate = Path(raw)
                if candidate.suffix:
                    return str(candidate.parent)
                return str(candidate)

            if normalized.startswith("/app/generated-sites/"):
                tail = normalized.removeprefix("/app/generated-sites/")
                slug = tail.split("/", 1)[0].strip()
                if slug:
                    return f"/app/generated-sites/{slug}"

            if normalized.startswith("/generated-sites/"):
                tail = normalized.removeprefix("/generated-sites/")
                slug = tail.split("/", 1)[0].strip()
                if slug:
                    return str((SandboxWriteManager.sandbox_root() / slug).resolve())

            return None

        candidates: list[str] = []
        artifact_history = session_metadata.get("artifact_history")
        if isinstance(artifact_history, list):
            for item in artifact_history:
                if not isinstance(item, dict):
                    continue
                artifact = (
                    item.get("artifact")
                    if isinstance(item.get("artifact"), dict)
                    else item
                )
                if not isinstance(artifact, dict):
                    continue
                for key in (
                    "sandbox_project_path",
                    "sandbox_target_path",
                    "project_path",
                    "target_path",
                    "preview_path",
                    "sandbox_relative_path",
                ):
                    value = artifact.get(key)
                    if isinstance(value, str):
                        normalized_candidate = _normalized_candidate_path(value)
                        if normalized_candidate:
                            candidates.append(normalized_candidate)
                written_paths = artifact.get("sandbox_written_paths")
                if isinstance(written_paths, list):
                    for entry in written_paths:
                        if isinstance(entry, str):
                            normalized_candidate = _normalized_candidate_path(entry)
                            if normalized_candidate:
                                candidates.append(normalized_candidate)
                project_slug = artifact.get("project_slug") or artifact.get(
                    "sandbox_project_slug"
                )
                if isinstance(project_slug, str) and project_slug.strip():
                    candidates.append(
                        str(
                            (
                                SandboxWriteManager.sandbox_root()
                                / project_slug.strip()
                            ).resolve()
                        )
                    )

        last_action = session_metadata.get("operator_last_action")
        if isinstance(last_action, dict):
            data = last_action.get("data")
            if isinstance(data, dict) and isinstance(data.get("project_path"), str):
                normalized_candidate = _normalized_candidate_path(
                    str(data["project_path"])
                )
                if normalized_candidate:
                    candidates.append(normalized_candidate)

        active_export = session_metadata.get("active_exported_artifact")
        if isinstance(active_export, dict):
            preferred_value = ""
            for key in (
                "host_project_path",
                "relative_project_path",
                "container_project_path",
            ):
                value = active_export.get(key)
                if isinstance(value, str) and value.strip():
                    preferred_value = value
                    break

            normalized_candidate = (
                _normalized_candidate_path(preferred_value) if preferred_value else None
            )
            if not normalized_candidate:
                project_slug = active_export.get("project_slug")
                if isinstance(project_slug, str) and project_slug.strip():
                    normalized_candidate = str(
                        (
                            SandboxWriteManager.sandbox_root() / project_slug.strip()
                        ).resolve()
                    )

            if normalized_candidate:
                candidates.append(normalized_candidate)

        last_payload = session_metadata.get("last_assistant_payload")
        if isinstance(last_payload, dict):
            artifact_patch = last_payload.get("artifact_patch_proposal")
            if isinstance(artifact_patch, dict):
                for key in ("target_path", "preview_path", "project_slug"):
                    value = artifact_patch.get(key)
                    if isinstance(value, str):
                        normalized_candidate = _normalized_candidate_path(value)
                        if normalized_candidate:
                            candidates.append(normalized_candidate)

            bundle = last_payload.get("site_bundle")
            if isinstance(bundle, dict):
                for key in (
                    "sandbox_project_path",
                    "sandbox_target_path",
                    "project_slug",
                ):
                    value = bundle.get(key)
                    if isinstance(value, str):
                        normalized_candidate = _normalized_candidate_path(value)
                        if normalized_candidate:
                            candidates.append(normalized_candidate)

            bundle_patches = last_payload.get("site_bundle_patch_proposals")
            if isinstance(bundle_patches, list):
                for patch in bundle_patches:
                    if not isinstance(patch, dict):
                        continue
                    for key in ("target_path", "preview_path", "project_slug"):
                        value = patch.get(key)
                        if isinstance(value, str):
                            normalized_candidate = _normalized_candidate_path(value)
                            if normalized_candidate:
                                candidates.append(normalized_candidate)

        return cls._dedup_paths(candidates)

    @staticmethod
    def _slugify_repo_name(value: str) -> str:
        return slugify_repo_name(value)

    @classmethod
    def _extract_repo_name_from_prompt(cls, source_text: str) -> str:
        return extract_repo_name_from_prompt(source_text)

    @classmethod
    def _missing_project_path_message(
        cls,
        *,
        candidate_paths: list[str],
        project_name_hint: str,
    ) -> str:
        return missing_project_path_message(
            candidate_paths=candidate_paths,
            project_name_hint=project_name_hint,
        )

    def _pending_operator_confirmation(
        self,
        *,
        question: str,
        reason: str,
        target: str,
        candidates: list[str] | None = None,
    ) -> OperatorExecution:
        now = datetime.now(UTC)
        action_id = self._next_action_id()
        data: dict[str, Any] = {
            "confirmation_needed": True,
            "reason": reason,
        }
        if candidates:
            data["candidates"] = candidates
        result = OperatorActionResult(
            action_id=action_id,
            action_name="operator_github_proof_project",
            mode="operator",
            status="pending",
            started_at=now,
            completed_at=now,
            command_or_operation="operator project workflow requires confirmation",
            target=target,
            stdout_summary="",
            stderr_summary=reason,
            exit_code=None,
            data=data,
            safety=OperatorSafety(
                allowed=True,
                read_only=False,
                mutates_files=True,
                mutates_git=True,
                requires_approval=True,
            ),
            receipt_label=f"operator_github_proof_project {action_id}",
        )
        answer = (
            "I can run that operator workflow, but I need one confirmation first. "
            f"{reason}"
        )
        return OperatorExecution(result=result, answer=answer, record_history=True)

    def _translate_first_class_slash(self, question: str) -> str:
        return translate_first_class_slash(question, self._parse_slash_command)

    @classmethod
    def _is_github_proof_project_request(cls, normalized: str) -> bool:
        return is_github_proof_project_request(normalized)

    def _natural_github_project_payload(
        self,
        question: str,
        normalized: str,
        session_metadata: dict[str, Any],
    ) -> tuple[str | None, str | None, list[str]]:
        source_text = self._strip_operator_mode_prefix(question).strip()
        lowered = self._strip_operator_mode_prefix(normalized)

        explicit_paths = self._extract_windows_paths(source_text)
        project_path = explicit_paths[0] if explicit_paths else ""
        candidate_paths = self._candidate_project_paths(session_metadata)
        if not project_path and len(candidate_paths) == 1:
            project_path = candidate_paths[0]

        if not project_path and len(candidate_paths) > 1:
            return (
                None,
                "I found multiple sandbox project candidates. Reply with the exact target path to continue push safely.",
                candidate_paths,
            )

        name_match = re.search(
            r"\bnamed\s+(.+?)(?:\s+under\b|\s+and\s+push\b|$)",
            source_text,
            flags=re.IGNORECASE,
        )
        project_name = name_match.group(1).strip() if name_match else ""
        if not project_name:
            active_export = session_metadata.get("active_exported_artifact")
            if isinstance(active_export, dict):
                project_slug = active_export.get("project_slug")
                if isinstance(project_slug, str) and project_slug.strip():
                    project_name = project_slug.strip()
        if not project_name and project_path:
            normalized_project_path = str(project_path).replace("\\", "/")
            project_name = normalized_project_path.rstrip("/").rsplit("/", 1)[-1]
        if project_name:
            project_name = self._slugify_repo_name(project_name)
        if not project_name:
            project_name = "github-proof-project"

        commit_match = re.search(
            r'commit\s+with\s+message\s+["\']([^"\']+)["\']',
            source_text,
            flags=re.IGNORECASE,
        )
        commit_message = (
            commit_match.group(1).strip()
            if commit_match
            else "build GitHub proof project"
        )

        repo_name = self._extract_repo_name_from_prompt(source_text) or project_name

        create_repo = (
            "create a github repo" in lowered
            or "create a new repository on github" in lowered
            or "create a new repo" in lowered
            or "new repo" in lowered
            or lowered.startswith("/github create")
            or lowered.startswith("/publish github")
        )
        push_requested = (
            "push to github" in lowered
            or "commit and push" in lowered
            or "build and push" in lowered
            or "real build and push" in lowered
            or "finish the github push" in lowered
            or lowered.startswith("/push")
            or lowered.startswith("/github push")
            or lowered.startswith("/publish github")
        )
        explicit_build_and_push = any(
            token in lowered
            for token in (
                "build and push",
                "real build and push",
                "build and push a real github proof project",
            )
        )
        write_project_files = explicit_build_and_push

        requested_files: list[str] = []
        for candidate in (
            "index.html",
            "assets/site.css",
            "assets/app.js",
            "README.md",
        ):
            if candidate.lower() in lowered:
                requested_files.append(candidate)
        if not requested_files:
            requested_files = [
                "index.html",
                "assets/site.css",
                "assets/app.js",
                "README.md",
            ]

        needs_existing_project = (
            create_repo or push_requested
        ) and not write_project_files
        if needs_existing_project and not project_path:
            return (
                None,
                self._missing_project_path_message(
                    candidate_paths=candidate_paths,
                    project_name_hint=project_name,
                ),
                candidate_paths,
            )

        payload: dict[str, Any] = {
            "prompt": source_text,
            "project_name": project_name,
            "project_path": project_path,
            "sandbox_project_path": project_path,
            "requested_files": requested_files,
            "commit_message": commit_message,
            "github_repo_name": repo_name,
            "initialize_git": True,
            "create_github_repo": create_repo,
            "push": push_requested,
            "write_project_files": write_project_files,
        }
        return json.dumps(payload), None, candidate_paths

    def _natural_commit_payload(self, normalized: str) -> str:
        commit_requested = any(
            token in normalized
            for token in (
                "commit",
                "commit it",
                "commit these changes",
                "commit the approved changes",
                "approve commit",
                "confirm commit",
                "make the commit",
                "create the commit",
                "go ahead and commit",
            )
        )
        push_requested = any(
            token in normalized
            for token in (
                "push",
                "push the branch",
                "git push",
                "commit and push",
            )
        )
        explicit_commit_approval = any(
            token in normalized
            for token in (
                "approved",
                "approve commit",
                "confirm commit",
                "commit these changes",
                "go ahead and commit",
            )
        )
        explicit_push_approval = any(
            token in normalized
            for token in (
                "approved to push",
                "approve push",
                "confirm push",
                "go ahead and push",
            )
        )

        mode = "apply" if (commit_requested or push_requested) else "preview"
        payload: dict[str, Any] = {
            "mode": mode,
            "push": push_requested,
            "approval": {"approved": explicit_commit_approval},
            "push_approval": {"approved": explicit_push_approval},
        }
        return json.dumps(payload)

    def _match_action(
        self, question: str, normalized: str
    ) -> tuple[str, str | None] | None:
        return OperatorChatRouterService(self).match_action(question, normalized)

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        return extract_json_object(text)

    def _natural_patch_payload(self, question: str, normalized: str) -> str | None:
        return OperatorChatRouterService(self)._natural_patch_payload(
            question, normalized
        )

    @staticmethod
    def _is_natural_validation_request(normalized: str) -> bool:
        return is_natural_validation_request(normalized)

    @staticmethod
    def _is_natural_repair_request(normalized: str) -> bool:
        return is_natural_repair_request(normalized)

    def _build_answer(self, action_name: str, result: OperatorActionResult) -> str:
        return build_operator_answer(action_name, result)

    def try_handle_chat(
        self,
        question: str,
        *,
        session_metadata: dict[str, Any] | None = None,
        operator_mode_enabled: bool = False,
    ) -> OperatorExecution | None:
        return OperatorChatRouterService(self).try_handle_chat(
            question,
            session_metadata=session_metadata,
            operator_mode_enabled=operator_mode_enabled,
        )
