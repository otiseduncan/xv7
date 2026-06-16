from __future__ import annotations

import json
from typing import Any

from core.operator.operator_intent import MUTATION_PATTERNS
from core.operator.operator_types import OperatorExecution


class OperatorChatRouterService:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

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
        payload = self._manager._extract_json_object(question) or {}
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

    def match_action(
        self, question: str, normalized: str
    ) -> tuple[str, str | None] | None:
        patch_payload = self._natural_patch_payload(question, normalized)
        if patch_payload is not None:
            return "operator_patch_report", patch_payload
        if self._manager._is_natural_repair_request(normalized):
            return "operator_repair_report", json.dumps(
                {
                    "profile": "python-core",
                    "max_cycles": 1,
                    "reason": question.strip(),
                }
            )
        if self._manager._is_natural_validation_request(normalized):
            return "operator_validation_report", json.dumps({"profile": "python-core"})
        if self._manager._is_commit_push_operator_request(normalized):
            return "operator_commit_report", self._manager._natural_commit_payload(
                normalized
            )
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
            return "read_project_file", self._manager._extract_read_target(question)
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

    def try_handle_chat(
        self,
        question: str,
        *,
        session_metadata: dict[str, Any] | None = None,
        operator_mode_enabled: bool = False,
    ) -> OperatorExecution | None:
        metadata = session_metadata or {}
        translated_question = self._manager._translate_first_class_slash(question)
        normalized = self._manager._normalize(translated_question)

        if self._manager._is_github_proof_project_request(normalized):
            payload, confirmation_reason, candidate_paths = (
                self._manager._natural_github_project_payload(
                    translated_question,
                    normalized,
                    metadata,
                )
            )
            if payload is None:
                pending_target = (
                    candidate_paths[0] if len(candidate_paths) == 1 else "sandbox"
                )
                return self._manager._pending_operator_confirmation(
                    question=translated_question,
                    reason=confirmation_reason
                    or "I need one explicit path confirmation before proceeding.",
                    target=pending_target,
                    candidates=candidate_paths,
                )

            result = self._manager._run_action(
                "operator_github_proof_project",
                action_id=self._manager._next_action_id(),
                repo_root=self._manager.repo_root,
                target=payload,
            )
            return OperatorExecution(
                result=result,
                answer=self._manager._build_answer(
                    "operator_github_proof_project", result
                ),
                record_history=True,
            )

        history_answer = self._manager._history_answer(normalized, metadata)
        if history_answer is not None:
            return history_answer

        if any(
            token in normalized for token in MUTATION_PATTERNS
        ) and not self._manager._is_non_mutation_writing_request(normalized):
            if self._manager._is_commit_proposal_request(normalized):
                return None
            if self._manager._is_commit_push_operator_request(normalized):
                action_name = "operator_commit_report"
                commit_target = self._manager._natural_commit_payload(normalized)
                result = self._manager._run_action(
                    action_name,
                    action_id=self._manager._next_action_id(),
                    repo_root=self._manager.repo_root,
                    target=commit_target,
                )
                return OperatorExecution(
                    result=result,
                    answer=self._manager._build_answer(action_name, result),
                    record_history=True,
                )
            denied = self._manager._denied_result(
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

        matched = self.match_action(translated_question, normalized)
        if matched is None:
            return None

        action_name, target = matched
        result = self._manager._run_action(
            action_name,
            action_id=self._manager._next_action_id(),
            repo_root=self._manager.repo_root,
            target=target,
        )
        return OperatorExecution(
            result=result,
            answer=self._manager._build_answer(action_name, result),
            record_history=True,
        )
