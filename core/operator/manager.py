from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.operator.history import get_history, latest_action, latest_action_by_name
from core.operator.registry import build_operator_registry, run_action
from core.operator.schema import (
    OperatorActionResult,
    OperatorMode,
    OperatorSafety,
    OperatorStatus,
)


MUTATION_PATTERNS = (
    "write",
    "edit",
    "delete",
    "remove",
    "commit",
    "push",
    "pull",
    "checkout",
    "reset",
    "git clean",
    "docker compose down",
    "docker compose up",
    "restart",
    "install",
    "create file",
)

NON_MUTATION_WRITING_PATTERNS = (
    "implementation prompt",
    "implementation prompts",
    "vs code prompt",
    "copilot prompt",
    "write a prompt",
    "write prompt",
    "app planning",
    "design architecture",
    "test planning",
    "debugging guidance",
    "documentation help",
    # Sandbox export/write intent: writing the active artifact to the approved sandbox
    # is allowed without Operator Mode — it is not repo mutation.
    "to the sandbox",
    "to sandbox",
    "export to sandbox",
    "save to sandbox",
    "write to sandbox",
)

FIRST_CLASS_SLASH_COMMANDS = {
    "/build",
    "/export",
    "/write",
    "/commit",
    "/push",
    "/github",
    "/publish",
}


@dataclass
class OperatorExecution:
    result: OperatorActionResult
    answer: str
    record_history: bool = True


@dataclass(frozen=True)
class SlashCommandSpec:
    slash: str
    category: str
    risk_level: str
    mode: str
    requires_typed_confirmation: bool = False
    confirmation_phrase: str | None = None
    reversible: bool = True
    implemented: bool = True


class OperatorManager:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self._counter = 0
        self.registry = build_operator_registry()
        self.pending_ttl_seconds = 300

        self.slash_commands: dict[str, SlashCommandSpec] = {
            "/scan-system": SlashCommandSpec(
                "/scan-system", "read_only_scan", "low", "read_only"
            ),
            "/scan-cpu": SlashCommandSpec(
                "/scan-cpu", "read_only_scan", "low", "read_only"
            ),
            "/scan-gpu": SlashCommandSpec(
                "/scan-gpu", "read_only_scan", "low", "read_only"
            ),
            "/scan-disk": SlashCommandSpec(
                "/scan-disk", "read_only_scan", "low", "read_only"
            ),
            "/scan-network": SlashCommandSpec(
                "/scan-network", "read_only_scan", "low", "read_only"
            ),
            "/scan-ports": SlashCommandSpec(
                "/scan-ports", "read_only_scan", "low", "read_only"
            ),
            "/scan-processes": SlashCommandSpec(
                "/scan-processes", "read_only_scan", "low", "read_only"
            ),
            "/scan-services": SlashCommandSpec(
                "/scan-services", "read_only_scan", "low", "read_only"
            ),
            "/scan-docker": SlashCommandSpec(
                "/scan-docker", "read_only_scan", "low", "read_only"
            ),
            "/scan-vscode": SlashCommandSpec(
                "/scan-vscode", "read_only_scan", "low", "read_only"
            ),
            "/scan-repo": SlashCommandSpec(
                "/scan-repo", "read_only_scan", "low", "read_only"
            ),
            "/list-disk": SlashCommandSpec(
                "/list-disk", "read_only_scan", "low", "read_only"
            ),
            "/list-disks": SlashCommandSpec(
                "/list-disks", "read_only_scan", "low", "read_only"
            ),
            "/list-drives": SlashCommandSpec(
                "/list-drives", "read_only_scan", "low", "read_only"
            ),
            "/list-files": SlashCommandSpec(
                "/list-files", "read_only_scan", "low", "read_only"
            ),
            "/read-file": SlashCommandSpec(
                "/read-file", "read_only_scan", "low", "read_only"
            ),
            "/search-files": SlashCommandSpec(
                "/search-files", "read_only_scan", "low", "read_only"
            ),
            "/run-tests": SlashCommandSpec(
                "/run-tests", "read_only_scan", "low", "read_only"
            ),
            "/build-task": SlashCommandSpec(
                "/build-task", "planning", "low", "operator"
            ),
            "/build": SlashCommandSpec(
                "/build", "project_workflow", "medium", "operator"
            ),
            "/export": SlashCommandSpec(
                "/export", "project_workflow", "medium", "operator"
            ),
            "/write": SlashCommandSpec(
                "/write", "project_workflow", "medium", "operator"
            ),
            "/commit": SlashCommandSpec(
                "/commit", "git_mutation", "medium", "operator"
            ),
            "/push": SlashCommandSpec(
                "/push", "git_mutation", "destructive", "operator"
            ),
            "/github": SlashCommandSpec(
                "/github", "git_mutation", "destructive", "operator"
            ),
            "/publish": SlashCommandSpec(
                "/publish", "git_mutation", "destructive", "operator"
            ),
            "/vscode-open-workspace": SlashCommandSpec(
                "/vscode-open-workspace",
                "vscode_read_only",
                "low",
                "read_only",
                implemented=False,
            ),
            "/vscode-open-file": SlashCommandSpec(
                "/vscode-open-file",
                "vscode_read_only",
                "low",
                "read_only",
                implemented=False,
            ),
            "/vscode-search": SlashCommandSpec(
                "/vscode-search",
                "vscode_read_only",
                "low",
                "read_only",
                implemented=False,
            ),
            "/vscode-diagnostics": SlashCommandSpec(
                "/vscode-diagnostics",
                "vscode_read_only",
                "low",
                "read_only",
                implemented=False,
            ),
            "/delete-file": SlashCommandSpec(
                "/delete-file", "mutation", "destructive", "operator"
            ),
            "/rename-file": SlashCommandSpec(
                "/rename-file", "mutation", "medium", "operator"
            ),
            "/move-file": SlashCommandSpec(
                "/move-file", "mutation", "medium", "operator", implemented=False
            ),
            "/copy-file": SlashCommandSpec(
                "/copy-file", "mutation", "medium", "operator", implemented=False
            ),
            "/write-file": SlashCommandSpec(
                "/write-file", "mutation", "medium", "operator"
            ),
            "/append-file": SlashCommandSpec(
                "/append-file", "mutation", "medium", "operator"
            ),
            "/create-folder": SlashCommandSpec(
                "/create-folder", "mutation", "medium", "operator"
            ),
            "/delete-folder": SlashCommandSpec(
                "/delete-folder",
                "mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/apply-patch": SlashCommandSpec(
                "/apply-patch", "mutation", "medium", "operator"
            ),
            "/restart-container": SlashCommandSpec(
                "/restart-container", "runtime_mutation", "medium", "operator"
            ),
            "/stop-container": SlashCommandSpec(
                "/stop-container",
                "runtime_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/start-container": SlashCommandSpec(
                "/start-container",
                "runtime_mutation",
                "medium",
                "operator",
                implemented=False,
            ),
            "/rebuild-container": SlashCommandSpec(
                "/rebuild-container",
                "runtime_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/restart-service": SlashCommandSpec(
                "/restart-service",
                "runtime_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/kill-process": SlashCommandSpec(
                "/kill-process",
                "runtime_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/git-add": SlashCommandSpec(
                "/git-add", "git_mutation", "medium", "operator", implemented=False
            ),
            "/git-commit": SlashCommandSpec(
                "/git-commit", "git_mutation", "medium", "operator", implemented=False
            ),
            "/git-push": SlashCommandSpec(
                "/git-push",
                "git_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/git-stash": SlashCommandSpec(
                "/git-stash", "git_mutation", "medium", "operator", implemented=False
            ),
            "/git-restore": SlashCommandSpec(
                "/git-restore",
                "git_mutation",
                "destructive",
                "operator",
                implemented=False,
            ),
            "/vscode-apply-patch": SlashCommandSpec(
                "/vscode-apply-patch",
                "vscode_mutation",
                "medium",
                "operator",
                implemented=False,
            ),
            "/vscode-write-file": SlashCommandSpec(
                "/vscode-write-file",
                "vscode_mutation",
                "medium",
                "operator",
                implemented=False,
            ),
            "/vscode-create-file": SlashCommandSpec(
                "/vscode-create-file",
                "vscode_mutation",
                "medium",
                "operator",
                implemented=False,
            ),
            "/format-drive": SlashCommandSpec(
                "/format-drive",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="FORMAT {target}",
                reversible=False,
                implemented=False,
            ),
            "/partition-info": SlashCommandSpec(
                "/partition-info",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="PARTITION INFO",
                reversible=False,
                implemented=False,
            ),
            "/git-reset-hard": SlashCommandSpec(
                "/git-reset-hard",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="RESET HARD",
                reversible=False,
                implemented=False,
            ),
            "/git-clean": SlashCommandSpec(
                "/git-clean",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="GIT CLEAN",
                reversible=False,
                implemented=False,
            ),
            "/delete-folder-recursive": SlashCommandSpec(
                "/delete-folder-recursive",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="DELETE {target}",
                reversible=False,
                implemented=False,
            ),
            "/stop-service": SlashCommandSpec(
                "/stop-service",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="STOP SERVICE",
                reversible=False,
                implemented=False,
            ),
            "/start-service": SlashCommandSpec(
                "/start-service",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="START SERVICE",
                reversible=False,
                implemented=False,
            ),
            "/change-firewall-rule": SlashCommandSpec(
                "/change-firewall-rule",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="CHANGE FIREWALL",
                reversible=False,
                implemented=False,
            ),
            "/registry-edit": SlashCommandSpec(
                "/registry-edit",
                "high_risk",
                "high",
                "operator",
                requires_typed_confirmation=True,
                confirmation_phrase="REGISTRY EDIT",
                reversible=False,
                implemented=False,
            ),
        }

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
        return "operator_pending_action"

    def get_pending_action(
        self, session_metadata: dict[str, Any]
    ) -> dict[str, Any] | None:
        pending = session_metadata.get(self._pending_key())
        if not isinstance(pending, dict):
            return None
        return pending

    def clear_pending_action(self, session_metadata: dict[str, Any]) -> None:
        session_metadata.pop(self._pending_key(), None)

    def _resolve_target_path(self, raw: str) -> Path:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.repo_root / candidate
        return candidate.resolve()

    def _path_allowed(self, path: Path) -> bool:
        allowed_roots = [self.repo_root, self.repo_root.parent]
        return any(root == path or root in path.parents for root in allowed_roots)

    def _parse_slash_command(self, command_text: str) -> tuple[str, list[str]]:
        if not command_text.strip().startswith("/"):
            raise ValueError("Slash command must start with '/'.")
        parts = shlex.split(command_text, posix=False)
        if not parts:
            raise ValueError("Command is empty.")
        return parts[0].lower(), parts[1:]

    @staticmethod
    def _looks_like_natural_language_request(text: str) -> bool:
        lowered = text.lower().strip()
        return any(
            token in lowered
            for token in (
                "we are in",
                "build this feature",
                "code 9",
                "code builder",
                "add tests",
                "pytest",
                "git commit",
                "git push",
                "feature request",
            )
        )

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
        normalized = command_text.strip()
        slash, args = self._parse_slash_command(normalized)
        spec = self.slash_commands.get(slash)
        if spec is None:
            result = self._build_result(
                action_name="unknown_slash_command",
                status="failed",
                command_preview=normalized,
                target=str(self.repo_root),
                stderr=f"Unknown slash command: {slash}",
            )
            return {
                "answer": f"Unknown slash command: {slash}",
                "result": result,
                "pending_action": None,
                "executed": False,
            }

        if slash == "/build-task" and not operator_mode:
            result = self._build_result(
                action_name="build_task",
                status="denied",
                mode_override="operator",
                command_preview=normalized,
                target=str(self.repo_root),
                stderr="/build-task requires Operator Mode.",
            )
            return {
                "answer": "/build-task requires Operator Mode. No files were changed. No tests were run. No commit or push occurred.",
                "result": result,
                "pending_action": None,
                "executed": False,
            }

        if slash in FIRST_CLASS_SLASH_COMMANDS:
            execution = self.try_handle_chat(
                command_text,
                session_metadata=session_metadata,
                operator_mode_enabled=True,
            )
            if execution is None:
                result = self._build_result(
                    action_name=slash.strip("/"),
                    status="failed",
                    command_preview=normalized,
                    target=str(self.repo_root),
                    stderr="Command was recognized but could not be routed.",
                    mutates_files=True,
                )
                return {
                    "answer": self._build_answer(result.action_name, result),
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
            result = self._build_result(
                action_name=slash.strip("/"),
                status="denied",
                command_preview=normalized,
                target=str(self.repo_root),
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
            result = self._build_task_plan_result(normalized, args)
            return {
                "answer": self._build_answer("build_task", result),
                "result": result,
                "pending_action": None,
                "executed": True,
            }

        if spec.mode == "read_only":
            result = self._read_only_scan_result(slash, args)
            return {
                "answer": self._build_answer(result.action_name, result),
                "result": result,
                "pending_action": None,
                "executed": True,
            }

        if slash == "/apply-patch":
            invalid = self._validate_apply_patch_stage_payload(normalized, args)
            if invalid is not None:
                return {
                    "answer": self._build_answer(invalid.action_name, invalid),
                    "result": invalid,
                    "pending_action": None,
                    "executed": True,
                }

        action_id = self._next_action_id()
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
                now.timestamp() + self.pending_ttl_seconds, tz=UTC
            ).isoformat(),
            "implemented": spec.implemented,
        }
        session_metadata[self._pending_key()] = pending_action

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
        answer = (
            "I'm ready to perform this operator action, but I need confirmation first."
        )
        return {
            "answer": answer,
            "result": result,
            "pending_action": pending_action,
            "executed": False,
        }

    def confirm_pending_action(
        self,
        pending_action: dict[str, Any] | None,
        *,
        typed_confirmation: str | None,
    ) -> dict[str, Any]:
        if not pending_action:
            result = self._build_result(
                action_name="operator_confirm",
                status="failed",
                command_preview="confirm pending operator action",
                target=str(self.repo_root),
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
                    result = self._build_result(
                        action_name=str(
                            pending_action.get("command_name", "operator_action")
                        ),
                        status="failed",
                        command_preview=str(pending_action.get("command_preview", "")),
                        target=str(pending_action.get("target", str(self.repo_root))),
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
                result = self._build_result(
                    action_name=str(
                        pending_action.get("command_name", "operator_action")
                    ),
                    status="failed",
                    mode_override="high_risk",
                    command_preview=str(pending_action.get("command_preview", "")),
                    target=str(pending_action.get("target", str(self.repo_root))),
                    stderr="Typed confirmation did not match.",
                    data={"typed_confirmation": "mismatch"},
                )
                return {
                    "answer": "Typed confirmation did not match. Action is still blocked.",
                    "result": result,
                }

        slash = "/" + str(pending_action.get("command_name", "")).lstrip("/")
        args = pending_action.get("arguments", [])
        spec = self.slash_commands.get(slash)
        if spec is None:
            result = self._build_result(
                action_name=str(pending_action.get("command_name", "operator_action")),
                status="failed",
                command_preview=str(pending_action.get("command_preview", "")),
                target=str(pending_action.get("target", str(self.repo_root))),
                stderr="Pending command no longer exists.",
            )
            return {"answer": "Pending command no longer exists.", "result": result}

        if not spec.implemented:
            result = self._build_result(
                action_name=str(pending_action.get("command_name", "operator_action")),
                status="not_implemented",
                mode_override="high_risk"
                if bool(pending_action.get("requires_typed_confirmation"))
                else "operator",
                command_preview=str(pending_action.get("command_preview", "")),
                target=str(pending_action.get("target", str(self.repo_root))),
                stderr="Action not implemented yet.",
                data={"typed_confirmation": "matched"}
                if bool(pending_action.get("requires_typed_confirmation"))
                else {},
                mutates_files=True,
            )
            return {"answer": "Action not implemented yet.", "result": result}

        result = self._execute_mutation(
            slash, list(args) if isinstance(args, list) else []
        )
        if result.status == "success":
            answer = f"Operator action {result.action_name} executed successfully."
        else:
            answer = self._build_answer(result.action_name, result)
        return {"answer": answer, "result": result}

    def cancel_pending_action(
        self, pending_action: dict[str, Any] | None
    ) -> dict[str, Any]:
        if not pending_action:
            result = self._build_result(
                action_name="operator_cancel",
                status="failed",
                command_preview="cancel pending operator action",
                target=str(self.repo_root),
                stderr="No pending operator action to cancel.",
            )
            return {"answer": "No pending operator action to cancel.", "result": result}

        result = OperatorActionResult(
            action_id=str(pending_action.get("action_id", self._next_action_id())),
            action_name=str(pending_action.get("command_name", "operator_action")),
            mode="high_risk"
            if bool(pending_action.get("requires_typed_confirmation"))
            else "operator",
            status="cancelled",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            command_or_operation=str(pending_action.get("command_preview", "cancel")),
            target=str(pending_action.get("target", str(self.repo_root))),
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

    def _next_action_id(self) -> str:
        self._counter += 1
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return f"OP-{stamp}-{self._counter:04d}"

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

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
        original = question.strip()
        if len(original) <= 5:
            return ""
        return original[5:].strip().strip(".")

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
        return any(token in normalized for token in NON_MUTATION_WRITING_PATTERNS)

    @staticmethod
    def _is_commit_proposal_request(normalized: str) -> bool:
        return any(
            token in normalized
            for token in (
                "prepare commit",
                "prepare a commit",
                "propose commit",
                "propose a commit",
                "commit proposal",
                "create commit proposal",
                "draft commit",
                "show commit proposal",
                "what would the commit be",
                "what should i commit",
                "commit it",
            )
        )

    @staticmethod
    def _is_commit_push_operator_request(normalized: str) -> bool:
        return any(
            token in normalized
            for token in (
                "commit the approved changes",
                "commit these changes",
                "commit the proposal",
                "approve commit",
                "confirm commit",
                "make the commit",
                "create the commit",
                "go ahead and commit",
                "push the branch",
                "push branch",
                "git push",
                "commit and push",
            )
        )

    @staticmethod
    def _strip_operator_mode_prefix(normalized: str) -> str:
        return re.sub(r"^operator\s+mode\s*:\s*", "", normalized, flags=re.IGNORECASE)

    @staticmethod
    def _extract_windows_paths(text: str) -> list[str]:
        return [
            match.strip().rstrip(".,;:)\"'")
            for match in re.findall(r"[A-Za-z]:\\[^\n\r\"']+", text or "")
        ]

    @classmethod
    def _is_first_class_operator_request(cls, normalized: str) -> bool:
        stripped = cls._strip_operator_mode_prefix(normalized)
        if any(stripped.startswith(prefix) for prefix in FIRST_CLASS_SLASH_COMMANDS):
            return True
        return cls._is_github_proof_project_request(
            stripped
        ) or cls._is_commit_push_operator_request(stripped)

    def is_first_class_operator_prompt(self, question: str) -> bool:
        normalized = self._normalize(self._translate_first_class_slash(question))
        return self._is_first_class_operator_request(normalized)

    @staticmethod
    def _dedup_paths(paths: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in paths:
            text = str(raw or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(text)
        return ordered

    @classmethod
    def _candidate_project_paths(cls, session_metadata: dict[str, Any]) -> list[str]:
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
                ):
                    value = artifact.get(key)
                    if isinstance(value, str):
                        candidates.append(value)

        last_action = session_metadata.get("operator_last_action")
        if isinstance(last_action, dict):
            data = last_action.get("data")
            if isinstance(data, dict) and isinstance(data.get("project_path"), str):
                candidates.append(str(data["project_path"]))

        return cls._dedup_paths(candidates)

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
        stripped = question.strip()
        if not stripped.startswith("/"):
            return stripped
        slash, args = self._parse_slash_command(stripped)
        lower_args = [arg.lower() for arg in args]

        if slash in {"/build", "/export", "/write"}:
            if "sandbox" in lower_args or not args:
                return "build the approved website to sandbox"
        if slash == "/commit":
            return "commit and push this project"
        if slash == "/push":
            if lower_args and lower_args[0] == "github":
                return "initialize the new repository and push to github"
            return "push to github"
        if slash == "/github":
            if lower_args and lower_args[0] == "create":
                repo_name = args[1] if len(args) > 1 else ""
                if repo_name:
                    return (
                        f"create a new repository on github named {repo_name} and push"
                    )
                return "create a new repository on github and push"
            if lower_args and lower_args[0] == "push":
                return "finish the github push for the existing proof project"
        if slash == "/publish" and lower_args and lower_args[0] == "github":
            return "create a new repository on github and push"
        return stripped

    @classmethod
    def _is_github_proof_project_request(cls, normalized: str) -> bool:
        stripped = cls._strip_operator_mode_prefix(normalized)
        return any(
            token in stripped
            for token in (
                "build and push",
                "push to github",
                "create a github repo",
                "create a new repository on github",
                "initialize the new repository and push to github",
                "initialize git",
                "git init",
                "commit and push",
                "commit and push this project",
                "finish the github push",
                "existing proof project",
                "real github proof project",
                "real build and push",
                "not a preview",
                "not a patch",
            )
        )

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

        needs_existing_project = any(
            token in lowered
            for token in (
                "initialize the new repository and push to github",
                "finish the github push",
                "existing proof project",
                "commit and push this project",
            )
        )
        if needs_existing_project and not project_path:
            return (
                None,
                "I need the sandbox project path to continue safely. Provide an explicit path like X:\\xoduz-sandbox\\earthx-github-proof.",
                candidate_paths,
            )

        name_match = re.search(
            r"\bnamed\s+([A-Za-z0-9._-]+)",
            source_text,
            flags=re.IGNORECASE,
        )
        project_name = name_match.group(1).strip() if name_match else ""
        if not project_name and project_path:
            project_name = Path(project_path).name
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

        repo_name_match = re.search(
            r"github\s+repo\s+([A-Za-z0-9._-]+)",
            source_text,
            flags=re.IGNORECASE,
        )
        repo_name = (
            repo_name_match.group(1).strip() if repo_name_match else project_name
        )

        write_project_files = not any(
            token in lowered
            for token in (
                "initialize the new repository and push to github",
                "finish the github push",
                "existing proof project",
                "commit and push this project",
            )
        )

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

        create_repo = (
            "create a github repo" in lowered
            or "create a new repository on github" in lowered
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

        payload: dict[str, Any] = {
            "prompt": source_text,
            "project_name": project_name,
            "project_path": project_path,
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
        patch_payload = self._natural_patch_payload(question, normalized)
        if patch_payload is not None:
            return "operator_patch_report", patch_payload
        if self._is_natural_repair_request(normalized):
            return "operator_repair_report", json.dumps(
                {
                    "profile": "python-core",
                    "max_cycles": 1,
                    "reason": question.strip(),
                }
            )
        if self._is_natural_validation_request(normalized):
            return "operator_validation_report", json.dumps({"profile": "python-core"})
        if self._is_commit_push_operator_request(normalized):
            return "operator_commit_report", self._natural_commit_payload(normalized)
        if normalized in {
            "check the repo.",
            "check the repo",
            "give me repo status.",
            "give me repo status",
            "repo status.",
            "repo status",
            "what is git status?",
            "what is git status",
        }:
            return "operator_status_report", None
        if normalized in {
            "what branch are we on?",
            "what branch are we on",
            "is the working tree clean?",
            "is the working tree clean",
        }:
            return "operator_status_report", None
        if normalized in {
            "list the project files.",
            "list the project files",
            "what files are in the project?",
            "what files are in the project",
        }:
            return "list_project_files", None
        if normalized.startswith("read "):
            return "read_project_file", self._extract_read_target(question)
        if normalized in {"is the runtime healthy?", "is the runtime healthy"}:
            return "runtime_health", None
        if normalized in {"are containers running?", "are containers running"}:
            return "scan_docker", None
        if normalized in {
            "what operator tools are available?",
            "what operator tools are available",
            "operator environment",
            "show operator environment",
        }:
            return "operator_environment", None
        if any(
            phrase in normalized
            for phrase in (
                "can you scan my system",
                "scan the local system",
                "scan my local system",
                "scan local system",
                "system scan",
                "system diagnostics",
                "hardware scan",
                "scan host",
                "host system",
                "show me the system inside",
                "show me the system information",
                "system info",
                "system information",
                "local system status",
            )
        ):
            return "scan_system", None
        if any(
            phrase in normalized
            for phrase in (
                "what processor am i running",
                "what cpu am i running",
                "scan cpu",
                "cpu scan",
                "cpu usage",
                "cpu load",
                "cpu temp",
                "cpu temperature",
                "cpu speed",
                "cpu status",
                "processor status",
                "processor temperature",
                "processor usage",
                "processor speed",
                "current load on my processor",
            )
        ):
            return "scan_cpu", None
        if any(
            phrase in normalized
            for phrase in (
                "what gpu am i running",
                "what gpus do i have",
                "what gpu do i have",
                "my gpu",
                "my gpus",
                "show me my gpu",
                "show my gpu",
                "show me my gpus",
                "show me the specs on my gpu",
                "show me the specs on my gpus",
                "gpu specs",
                "graphics card specs",
                "graphics card info",
                "graphics card information",
                "my graphics card",
                "what graphics card",
                "scan gpu",
                "gpu scan",
                "gpu usage",
                "gpu speed",
                "gpu status",
                "gpu temp",
                "gpu temperature",
                "graphics card status",
                "graphics temperature",
                "video card temperature",
                "vram usage",
            )
        ):
            return "scan_gpu", None
        if any(
            phrase in normalized
            for phrase in (
                "how many drives does the local system have",
                "how many drives are on the local system",
                "how many drives do i have",
                "how many drives",
                "what drives do i have",
                "show my drives",
                "show me my drives",
                "my drives",
                "drive info",
                "drive information",
                "storage info",
                "storage information",
                "show drives",
                "scan disk",
                "scan disks",
                "list disk",
                "list disks",
                "list disc",
                "list discs",
                "list drives",
                "show local drives",
                "disk usage",
                "drive usage",
                "disk space",
                "drive space",
                "storage space",
                "how much space is left on the local drive",
                "free space",
            )
        ):
            return "scan_disk", None
        if any(
            phrase in normalized
            for phrase in (
                "scan network",
                "network scan",
                "network diagnostics",
                "ip configuration",
                "scan adapters",
            )
        ):
            return "scan_network", None
        if any(
            phrase in normalized
            for phrase in (
                "scan ports",
                "open ports",
                "listening ports",
                "port scan",
            )
        ):
            return "scan_ports", None
        if any(
            phrase in normalized
            for phrase in (
                "scan processes",
                "running processes",
                "top processes",
                "process list",
            )
        ):
            return "scan_processes", None
        if any(
            phrase in normalized
            for phrase in (
                "scan services",
                "service status",
                "running services",
                "windows services",
            )
        ):
            return "scan_services", None
        if any(
            phrase in normalized
            for phrase in (
                "scan docker",
                "docker scan",
                "docker status",
                "docker containers",
                "container status",
            )
        ):
            return "scan_docker", None
        if any(
            phrase in normalized
            for phrase in (
                "scan vscode",
                "vscode status",
                "vs code status",
                "vscode extensions",
                "vs code extensions",
            )
        ):
            return "scan_vscode", None
        if normalized in {"summarize logs.", "summarize logs"}:
            return "logs_summary", None
        if normalized in {"audit memory.", "audit memory"}:
            return "memory_audit", None
        if normalized in {
            "recent commits",
            "show recent commits",
            "repo recent commits",
        }:
            return "repo_recent_commits", None
        return None

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _natural_patch_payload(self, question: str, normalized: str) -> str | None:
        is_preview = any(
            phrase in normalized
            for phrase in (
                "preview this patch",
                "preview the patch",
                "show patch preview",
            )
        )
        is_apply = any(
            phrase in normalized
            for phrase in (
                "apply this patch",
                "apply the patch",
                "apply this approved patch",
                "apply approved patch",
            )
        )
        if not (is_preview or is_apply):
            return None
        payload = self._extract_json_object(question) or {}
        if not payload:
            payload = {"changes": []}
        payload = dict(payload)
        payload["mode"] = "preview" if is_preview else "apply"
        if is_apply and "approved patch" in normalized and "approval" not in payload:
            payload["approval"] = {
                "approved": True,
                "source": "natural-language explicit approval",
            }
        return json.dumps(payload)

    @staticmethod
    def _is_natural_validation_request(normalized: str) -> bool:
        return normalized in {
            "run validation.",
            "run validation",
            "run the checks.",
            "run the checks",
            "run checks.",
            "run checks",
            "what's failing?",
            "what's failing",
            "what is failing?",
            "what is failing",
        }

    @staticmethod
    def _is_natural_repair_request(normalized: str) -> bool:
        return normalized in {
            "fix the first failure.",
            "fix the first failure",
            "fix first failure.",
            "fix first failure",
            "fix it.",
            "fix it",
        }

    def _build_answer(self, action_name: str, result: OperatorActionResult) -> str:
        if action_name in {"build_task", "patch_plan"}:
            data = result.data if isinstance(result.data, dict) else {}
            goal = str(data.get("goal", "")).strip() or "(missing goal)"
            reason = str(data.get("reason", "")).strip()
            likely_files = data.get("likely_files", [])
            if not isinstance(likely_files, list):
                likely_files = []
            likely_files = [str(item) for item in likely_files if str(item).strip()]
            tests_to_run = data.get("tests_to_run", [])
            if not isinstance(tests_to_run, list):
                tests_to_run = []
            tests_to_run = [str(item) for item in tests_to_run if str(item).strip()]
            risk = str(data.get("risk", "unknown")).strip() or "unknown"
            risk_reason = (
                str(data.get("risk_reason", "No risk notes available.")).strip()
                or "No risk notes available."
            )
            workspace_summary = (
                data.get("workspace_summary", {})
                if isinstance(data.get("workspace_summary", {}), dict)
                else {}
            )
            branch = (
                str(workspace_summary.get("branch", "unknown")).strip() or "unknown"
            )
            dirty_count = int(workspace_summary.get("dirty_file_count", 0) or 0)

            inspect_text = ", ".join(likely_files[:10]) if likely_files else "(none)"
            change_text = ", ".join(likely_files[:10]) if likely_files else "(none)"
            tests_text = ", ".join(tests_to_run[:8]) if tests_to_run else "(none)"
            validation_text = tests_text
            next_step = (
                "prepare a patch payload"
                if bool(data.get("mutation_required", False))
                else "use VS Code/Copilot to implement the plan"
            )

            return (
                "Build Plan\n"
                f"Task summary: {goal}\n"
                f"Reason: {reason or 'No specific scope reason was available.'}\n"
                f"Files/directories inspected or recommended for inspection: {inspect_text}\n"
                f"Likely files to change: {change_text}\n"
                f"Tests to add/update: {tests_text}\n"
                f"Validation commands: {validation_text}\n"
                f"Risk notes: risk={risk}; {risk_reason}; branch={branch}; dirty_file_count={dirty_count}.\n"
                "No files were changed. No tests were run. No commit or push occurred.\n"
                f"Next valid operator step: {next_step} or use VS Code/Copilot to implement the plan."
            )

        if action_name == "docker_compose_ps" and result.status == "failed":
            return (
                "Container status cannot be proven from inside xv7-core because Docker CLI/socket is unavailable. "
                "No action was run beyond the read-only availability check."
            )
        if action_name.startswith("scan_") and result.status == "failed":
            limitation = str(result.data.get("limitation") or "").strip()
            limitation_lower = limitation.lower()
            if (
                "bridge is not running" in limitation_lower
                or "local host scan bridge" in limitation_lower
            ):
                return "I can check that through the local host scan bridge, but the bridge is not running yet."
            if limitation:
                return f"Host scan failed: {limitation}"
            return (
                "Host scan failed. "
                f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
            )
        if action_name == "operator_validation_report":
            passed = bool(result.data.get("passed", False))
            commands = result.data.get("selected_commands", [])
            command_count = len(commands) if isinstance(commands, list) else 0
            if passed:
                return (
                    f"Validation passed for {command_count} allowlisted command(s). "
                    "No files were changed. No commit or push occurred."
                )
            first_failure = str(result.data.get("first_failure_command") or "unknown")
            return (
                f"Validation failed. First failing command: {first_failure}. "
                "No files were changed. No commit or push occurred."
            )
        if action_name == "operator_patch_report":
            changed_files = result.data.get("changed_files", [])
            changed_count = len(changed_files) if isinstance(changed_files, list) else 0
            if result.status == "denied":
                return (
                    "Patch request was denied by safety policy. "
                    f"Safe detail: {result.stderr_summary or 'no detail available.'} "
                    "No commit or push occurred."
                )
            mode = str(result.data.get("mode") or "preview")
            if mode == "preview":
                return (
                    f"Patch preview completed for {changed_count} changed file(s). "
                    "No files were changed. No commit or push occurred."
                )
            return (
                f"Patch apply completed for {changed_count} changed file(s). "
                "No commit or push occurred."
            )
        if action_name == "operator_commit_report":
            candidate_files = result.data.get("candidate_files", [])
            committed_files = result.data.get("committed_files", [])
            skipped_files = result.data.get("skipped_files", [])
            commit_message = str(result.data.get("commit_message") or "").strip()
            commit_sha = str(result.data.get("commit_sha") or "").strip()
            pushed = bool(result.data.get("pushed", False))
            mode = str(result.data.get("mode") or "preview")
            if result.status == "denied" and result.safety.requires_approval:
                return (
                    "Commit/push request requires explicit approval before mutation. "
                    "No merge was performed."
                )
            if result.status == "denied":
                return (
                    "Commit/push request was blocked by safety policy. "
                    f"Safe detail: {result.stderr_summary or 'no detail available.'}"
                )
            if mode == "preview" and result.status == "success":
                return (
                    f"Commit/push preview prepared with {len(candidate_files)} candidate file(s), "
                    f"{len(skipped_files)} skipped file(s), and commit message '{commit_message}'. "
                    "Approval is required before commit or push."
                )
            if result.status == "success":
                return (
                    f"Commit workflow completed for {len(committed_files)} file(s); "
                    f"commit_sha={commit_sha or 'n/a'}; pushed={str(pushed).lower()}. "
                    "No merge was performed."
                )
            return (
                "Commit/push workflow failed. "
                f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
            )
        if action_name == "operator_repair_report":
            if result.status == "denied":
                return (
                    "Repair cycle was denied by safety policy. "
                    f"Safe detail: {result.stderr_summary or 'no detail available.'} "
                    "No commit or push occurred."
                )
            if result.status == "failed":
                first_failure = str(
                    result.data.get("first_failure_command") or "unknown"
                )
                return (
                    f"Repair cycle did not complete successfully. First failure: {first_failure}. "
                    "A concrete approved patch is required when no safe patch is supplied. "
                    "No commit or push occurred."
                )
            return (
                "Repair cycle completed. "
                "No commit or push occurred; commit/push still require separate approval."
            )
        if action_name == "operator_github_proof_project":
            if result.status == "success":
                commit_sha = str(result.data.get("commit_sha") or "").strip() or "n/a"
                pushed = bool(result.data.get("pushed", False))
                project_path = str(result.data.get("project_path") or result.target)
                branch = str(result.data.get("branch") or "").strip() or "unknown"
                remotes = result.data.get("remotes", [])
                remote_count = len(remotes) if isinstance(remotes, list) else 0
                status_lines = result.data.get("status_lines", [])
                status_count = (
                    len(status_lines) if isinstance(status_lines, list) else 0
                )
                return (
                    f"Sandbox project workflow completed at {project_path}; "
                    f"branch={branch}; commit_sha={commit_sha}; remotes={remote_count}; "
                    f"status_entries={status_count}; pushed={str(pushed).lower()}."
                )
            if result.status == "pending":
                return (
                    "Operator GitHub workflow is staged pending confirmation. "
                    f"Detail: {result.stderr_summary or 'confirmation is required.'}"
                )
            failed_command = str(result.data.get("failed_command") or "").strip()
            repo_before = (
                result.data.get("repo_before", {})
                if isinstance(result.data.get("repo_before", {}), dict)
                else {}
            )
            branch = str(repo_before.get("branch") or "").strip() or "unknown"
            remotes = repo_before.get("remotes", [])
            remote_count = len(remotes) if isinstance(remotes, list) else 0
            status_lines = repo_before.get("status_lines", [])
            status_count = len(status_lines) if isinstance(status_lines, list) else 0
            if failed_command:
                return (
                    "GitHub proof project workflow failed. "
                    f"Failed command: {failed_command}. "
                    f"Detail: {result.stderr_summary or 'no stderr detail available.'} "
                    f"Repo state: branch={branch}; remotes={remote_count}; status_entries={status_count}."
                )
            return (
                "GitHub proof project workflow failed. "
                f"Detail: {result.stderr_summary or 'no stderr detail available.'} "
                f"Repo state: branch={branch}; remotes={remote_count}; status_entries={status_count}."
            )
        if result.status == "failed":
            return (
                f"Operator action {result.action_name} failed. "
                f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
            )
        if result.status == "denied":
            return (
                "The requested operator action was denied by read-only safety policy."
            )

        if action_name in {"repo_status", "operator_status_report"}:
            branch = str(result.data.get("branch", "unknown"))
            clean = bool(result.data.get("clean", False))
            clean_text = "clean" if clean else "not clean"
            sync = str(result.data.get("sync", "unknown"))
            upstream = result.data.get("upstream")
            if upstream:
                return (
                    f"Repo is on {branch} tracking {upstream}; "
                    f"working tree is {clean_text}; sync={sync}."
                )
            return f"Repo is on {branch}; working tree is {clean_text}; sync={sync}."
        if action_name == "repo_recent_commits":
            commits = result.data.get("commits", [])
            if not commits:
                return "No recent commit lines were returned."
            return "Recent commits:\n" + "\n".join(f"- {item}" for item in commits)
        if action_name == "list_project_files":
            files = result.data.get("files", [])
            listed = files[:20]
            return "Project files (first 20):\n" + "\n".join(
                f"- {item}" for item in listed
            )
        if action_name == "read_project_file":
            if result.status == "denied":
                return "Read denied: requested path is outside repo root."
            if result.status == "failed":
                return "File read failed: target file was not found."
            path = str(result.data.get("path", "unknown"))
            content = str(result.data.get("content", "")).strip()
            return f"Read {path}:\n{content}"
        if action_name == "runtime_health":
            health = (
                result.data.get("health", {}) if isinstance(result.data, dict) else {}
            )
            runtime_ok = (
                bool(result.data.get("runtime_status"))
                if isinstance(result.data, dict)
                else False
            )
            checked_from = (
                result.data.get("checked_from", "unknown")
                if isinstance(result.data, dict)
                else "unknown"
            )
            return (
                f"Runtime health check: checked_from={checked_from}; "
                f"health={health.get('status', 'unknown')}; runtime_status_loaded={runtime_ok}."
            )
        if action_name == "docker_compose_ps":
            containers = result.data.get("containers", [])
            if not containers:
                return "No running containers were reported by docker compose ps."
            names = []
            for item in containers[:10]:
                if isinstance(item, dict):
                    names.append(str(item.get("Name", "unknown")))
            return "Containers reported by compose: " + ", ".join(names)
        if action_name == "operator_environment":
            git_available = bool(result.data.get("git_available", False))
            docker_cli_available = bool(result.data.get("docker_cli_available", False))
            docker_socket_available = bool(
                result.data.get("docker_socket_available", False)
            )
            return (
                "Operator environment (read-only): "
                f"git_available={git_available}, "
                f"docker_cli_available={docker_cli_available}, "
                f"docker_socket_available={docker_socket_available}."
            )
        if action_name == "scan_system":
            scan = result.data.get("result", {})
            if isinstance(scan, dict):
                os_name = str(scan.get("os_name") or "unknown")
                hostname = str(scan.get("hostname") or "unknown")
                uptime = scan.get("uptime_seconds")
                return f"System info: host={hostname}; os={os_name}; uptime_seconds={uptime}."
            return "Host system scan completed."
        if action_name == "scan_cpu":
            scan = result.data.get("result", {})
            if isinstance(scan, dict):
                name = str(scan.get("name") or "unknown")
                load = scan.get("load_percent")
                speed = scan.get("current_clock_mhz")
                return f"CPU status: {name}; load_percent={load}; current_clock_mhz={speed}."
            return "CPU scan completed."
        if action_name == "scan_gpu":
            scan = result.data.get("result", {})
            if isinstance(scan, dict):
                gpus = scan.get("gpus")
                if isinstance(gpus, list) and gpus:
                    first = gpus[0] if isinstance(gpus[0], dict) else {}
                    name = str(first.get("name") or "unknown")
                    temp = first.get("temperature_c")
                    util = first.get("utilization_percent")
                    return f"GPU status: {name}; temperature_c={temp}; utilization_percent={util}; gpu_count={len(gpus)}."
            return "GPU scan completed."
        if action_name == "scan_disk":
            scan = result.data.get("result", {})
            if isinstance(scan, dict):
                drives = scan.get("drives")
                if isinstance(drives, list):
                    count = len(drives)
                    preview = []
                    for item in drives[:4]:
                        if isinstance(item, dict):
                            drive = str(item.get("drive") or "?")
                            free_bytes = item.get("free_bytes")
                            preview.append(f"{drive} free_bytes={free_bytes}")
                    preview_text = "; ".join(preview)
                    return f"Disk status: drives={count}. {preview_text}".strip()
            return "Disk scan completed."
        if action_name == "scan_network":
            return "Network scan completed."
        if action_name == "scan_ports":
            return "Port scan completed."
        if action_name == "scan_processes":
            return "Process scan completed."
        if action_name == "scan_services":
            return "Service scan completed."
        if action_name == "scan_docker":
            return "Docker host scan completed."
        if action_name == "scan_vscode":
            return "VS Code host scan completed."
        if action_name == "logs_summary":
            logs = result.data.get("logs", [])
            if not logs:
                return "No log files found to summarize."
            parts = []
            for item in logs:
                if isinstance(item, dict):
                    parts.append(
                        f"{item.get('file', 'unknown')} (lines={item.get('line_count', 0)})"
                    )
            return "Log summary: " + "; ".join(parts)
        if action_name == "memory_audit":
            counts = result.data.get("status_counts", {})
            return (
                "Memory audit: "
                f"active={counts.get('active', 0)}, "
                f"deleted={counts.get('deleted', 0)}, "
                f"superseded={counts.get('superseded', 0)}."
            )
        return "Operator action completed."

    def try_handle_chat(
        self,
        question: str,
        *,
        session_metadata: dict[str, Any] | None = None,
        operator_mode_enabled: bool = False,
    ) -> OperatorExecution | None:
        metadata = session_metadata or {}
        translated_question = self._translate_first_class_slash(question)
        normalized = self._normalize(translated_question)

        if self._is_github_proof_project_request(normalized):
            payload, confirmation_reason, candidate_paths = (
                self._natural_github_project_payload(
                    translated_question,
                    normalized,
                    metadata,
                )
            )
            if payload is None:
                pending_target = (
                    candidate_paths[0] if len(candidate_paths) == 1 else "sandbox"
                )
                return self._pending_operator_confirmation(
                    question=translated_question,
                    reason=confirmation_reason
                    or "I need one explicit path confirmation before proceeding.",
                    target=pending_target,
                    candidates=candidate_paths,
                )

            result = run_action(
                "operator_github_proof_project",
                action_id=self._next_action_id(),
                repo_root=self.repo_root,
                target=payload,
            )
            return OperatorExecution(
                result=result,
                answer=self._build_answer("operator_github_proof_project", result),
                record_history=True,
            )

        history_answer = self._history_answer(normalized, metadata)
        if history_answer is not None:
            return history_answer

        if any(
            token in normalized for token in MUTATION_PATTERNS
        ) and not self._is_non_mutation_writing_request(normalized):
            if self._is_commit_proposal_request(normalized):
                return None
            if self._is_commit_push_operator_request(normalized):
                action_name = "operator_commit_report"
                commit_target = self._natural_commit_payload(normalized)
                result = run_action(
                    action_name,
                    action_id=self._next_action_id(),
                    repo_root=self.repo_root,
                    target=commit_target,
                )
                return OperatorExecution(
                    result=result,
                    answer=self._build_answer(action_name, result),
                    record_history=True,
                )
            denied = self._denied_result(
                question,
                "Mutation requires explicit command intent and may require staged confirmation.",
            )
            return OperatorExecution(
                result=denied,
                answer=(
                    "This is an implementation/repo mutation task. "
                    "Provide an explicit operator command (verbal or slash). "
                    "For risky or ambiguous mutations, staged confirmation is required before execution. "
                    "No files were changed. No tests were run. No commit or push occurred."
                ),
                record_history=True,
            )

        matched = self._match_action(translated_question, normalized)
        if matched is None:
            return None

        action_name, target = matched
        result = run_action(
            action_name,
            action_id=self._next_action_id(),
            repo_root=self.repo_root,
            target=target,
        )
        return OperatorExecution(
            result=result,
            answer=self._build_answer(action_name, result),
            record_history=True,
        )
