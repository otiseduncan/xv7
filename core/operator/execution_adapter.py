from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from core.operator.schema import OperatorActionResult


class OperatorExecutionAdapter:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def validate_apply_patch_stage_payload(
        self, command_preview: str, args: list[str]
    ) -> OperatorActionResult | None:
        payload_text = " ".join(args).strip()
        invalid_payload_message = (
            "Invalid patch payload. /apply-patch requires a valid approved patch payload, "
            "not a natural-language build request."
        )

        if not payload_text:
            return self._manager._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            if self._manager._looks_like_natural_language_request(payload_text):
                return self._manager._build_result(
                    action_name="apply_patch",
                    status="failed",
                    command_preview=command_preview,
                    target=str(self._manager.repo_root),
                    stderr=invalid_payload_message,
                    mutates_files=True,
                    requires_approval=True,
                )
            return self._manager._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        if not isinstance(payload, dict):
            return self._manager._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        has_change_shape = isinstance(payload.get("changes"), list) or isinstance(
            payload.get("path"), str
        )
        if not has_change_shape:
            return self._manager._build_result(
                action_name="apply_patch",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr=invalid_payload_message,
                mutates_files=True,
                requires_approval=True,
            )

        return None

    def read_only_scan_result(
        self, slash: str, args: list[str]
    ) -> OperatorActionResult:
        if slash == "/scan-repo":
            return self._manager._run_action(
                "repo_status",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-system":
            return self._manager._run_action(
                "scan_system",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-cpu":
            return self._manager._run_action(
                "scan_cpu",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-gpu":
            return self._manager._run_action(
                "scan_gpu",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash in {"/scan-disk", "/list-disk", "/list-disks", "/list-drives"}:
            return self._manager._run_action(
                "scan_disk",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-network":
            return self._manager._run_action(
                "scan_network",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-ports":
            return self._manager._run_action(
                "scan_ports",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-processes":
            return self._manager._run_action(
                "scan_processes",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-services":
            return self._manager._run_action(
                "scan_services",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-docker":
            return self._manager._run_action(
                "scan_docker",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/scan-vscode":
            return self._manager._run_action(
                "scan_vscode",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/list-files":
            return self._manager._run_action(
                "list_project_files",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
            )
        if slash == "/read-file":
            if not args:
                return self._manager._build_result(
                    action_name="read_file",
                    status="failed",
                    command_preview="read project file",
                    target=str(self._manager.repo_root),
                    stderr="Missing target path. Usage: /read-file <path>",
                )
            return self._manager._run_action(
                "read_project_file",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
                target=args[0],
            )
        if slash == "/search-files":
            if not args:
                return self._manager._build_result(
                    action_name="search_files",
                    status="failed",
                    command_preview="search project files",
                    target=str(self._manager.repo_root),
                    stderr="Missing search query. Usage: /search-files <text>",
                )
            query = args[0].lower()
            files = sorted(
                str(path.relative_to(self._manager.repo_root)).replace("\\", "/")
                for path in self._manager.repo_root.rglob("*")
                if path.is_file()
                and query in str(path).lower()
                and ".git" not in path.parts
            )[:60]
            return self._manager._build_result(
                action_name="search_files",
                status="success",
                command_preview=f"search files for '{query}'",
                target=str(self._manager.repo_root),
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
                return self._manager._run_action(
                    "test_runner",
                    action_id=self._manager._next_action_id(),
                    repo_root=self._manager.repo_root,
                    target=target,
                )
            except ValueError as exc:
                return self._manager._build_result(
                    action_name="run_tests",
                    status="failed",
                    command_preview="run allowlisted tests",
                    target=str(self._manager.repo_root),
                    stderr=str(exc),
                )
        return self._manager._build_result(
            action_name=slash.strip("/"),
            status="failed",
            command_preview=slash,
            target=str(self._manager.repo_root),
            stderr="Action not implemented yet.",
        )

    def build_task_plan_result(
        self, command_preview: str, args: list[str]
    ) -> OperatorActionResult:
        goal = " ".join(args).strip()
        if not goal:
            return self._manager._build_result(
                action_name="build_task",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr="Missing build task request. Usage: /build-task <natural-language request>",
            )

        try:
            return self._manager._run_action(
                "patch_plan",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
                target=goal,
            )
        except ValueError as exc:
            return self._manager._build_result(
                action_name="build_task",
                status="failed",
                command_preview=command_preview,
                target=str(self._manager.repo_root),
                stderr=str(exc),
            )

    def execute_mutation(self, slash: str, args: list[str]) -> OperatorActionResult:
        if slash == "/delete-file":
            if not args:
                return self._manager._build_result(
                    action_name="delete_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Missing path argument.",
                    mutates_files=True,
                )
            target = self._manager._resolve_target_path(args[0])
            if not self._manager._path_allowed(target):
                return self._manager._build_result(
                    action_name="delete_file",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            if not target.exists() or not target.is_file():
                return self._manager._build_result(
                    action_name="delete_file",
                    status="failed",
                    command_preview=slash,
                    target=str(target),
                    stderr="File not found.",
                    mutates_files=True,
                )
            target.unlink()
            return self._manager._build_result(
                action_name="delete_file",
                status="success",
                command_preview=f'Remove-Item "{target}"',
                target=str(target),
                stdout="file deleted",
                mutates_files=True,
            )

        if slash == "/rename-file":
            if len(args) < 2:
                return self._manager._build_result(
                    action_name="rename_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Usage: /rename-file <old> <new>",
                    mutates_files=True,
                )
            src = self._manager._resolve_target_path(args[0])
            dst = self._manager._resolve_target_path(args[1])
            if not self._manager._path_allowed(src) or not self._manager._path_allowed(
                dst
            ):
                return self._manager._build_result(
                    action_name="rename_file",
                    status="denied",
                    command_preview=slash,
                    target=str(src),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            if not src.exists() or not src.is_file():
                return self._manager._build_result(
                    action_name="rename_file",
                    status="failed",
                    command_preview=slash,
                    target=str(src),
                    stderr="Source file not found.",
                    mutates_files=True,
                )
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return self._manager._build_result(
                action_name="rename_file",
                status="success",
                command_preview=f'Rename-Item "{src}" "{dst.name}"',
                target=str(dst),
                stdout="file renamed",
                mutates_files=True,
            )

        if slash == "/create-folder":
            if not args:
                return self._manager._build_result(
                    action_name="create_folder",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Missing folder path.",
                    mutates_files=True,
                )
            target = self._manager._resolve_target_path(args[0])
            if not self._manager._path_allowed(target):
                return self._manager._build_result(
                    action_name="create_folder",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            target.mkdir(parents=True, exist_ok=True)
            return self._manager._build_result(
                action_name="create_folder",
                status="success",
                command_preview=f'New-Item -ItemType Directory -Path "{target}"',
                target=str(target),
                stdout="folder created",
                mutates_files=True,
            )

        if slash == "/write-file":
            if len(args) < 2:
                return self._manager._build_result(
                    action_name="write_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Usage: /write-file <path> <content>",
                    mutates_files=True,
                )
            target = self._manager._resolve_target_path(args[0])
            content = " ".join(args[1:])
            if not self._manager._path_allowed(target):
                return self._manager._build_result(
                    action_name="write_file",
                    status="denied",
                    command_preview=slash,
                    target=str(target),
                    stderr="Denied outside allowed workspace roots.",
                    mutates_files=True,
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return self._manager._build_result(
                action_name="write_file",
                status="success",
                command_preview=f'Set-Content "{target}"',
                target=str(target),
                stdout=f"wrote {len(content)} chars",
                mutates_files=True,
            )

        if slash == "/append-file":
            if len(args) < 2:
                return self._manager._build_result(
                    action_name="append_file",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Usage: /append-file <path> <content>",
                    mutates_files=True,
                )
            target = self._manager._resolve_target_path(args[0])
            content = " ".join(args[1:])
            if not self._manager._path_allowed(target):
                return self._manager._build_result(
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
            return self._manager._build_result(
                action_name="append_file",
                status="success",
                command_preview=f'Add-Content "{target}"',
                target=str(target),
                stdout=f"appended {len(content)} chars",
                mutates_files=True,
            )

        if slash == "/restart-container":
            if not args:
                return self._manager._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=slash,
                    target=str(self._manager.repo_root),
                    stderr="Usage: /restart-container <name>",
                    mutates_runtime=True,
                )
            container_name = args[0]
            docker_cli = shutil.which("docker")
            if not docker_cli:
                return self._manager._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=slash,
                    target=container_name,
                    stderr="Docker CLI unavailable.",
                    mutates_runtime=True,
                )
            proc = subprocess.run(
                ["docker", "compose", "restart", container_name],
                cwd=str(self._manager.repo_root),
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                return self._manager._build_result(
                    action_name="restart_container",
                    status="failed",
                    command_preview=f"docker compose restart {container_name}",
                    target=container_name,
                    stderr=proc.stderr[:400] or "restart failed",
                    mutates_runtime=True,
                )
            return self._manager._build_result(
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
                return self._manager._run_action(
                    "apply_approved_patch",
                    action_id=self._manager._next_action_id(),
                    repo_root=self._manager.repo_root,
                    target=patch_payload,
                )
            except ValueError as exc:
                return self._manager._build_result(
                    action_name="apply_patch",
                    status="failed",
                    command_preview="approval-gated patch apply",
                    target=str(self._manager.repo_root),
                    stderr=str(exc),
                    mutates_files=True,
                    requires_approval=True,
                )

        return self._manager._build_result(
            action_name=slash.strip("/"),
            status="failed",
            command_preview=slash,
            target=str(self._manager.repo_root),
            stderr="Action not implemented yet.",
            mutates_files=True,
        )
