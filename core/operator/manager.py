from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.operator.history import get_history, latest_action, latest_action_by_name
from core.operator.registry import build_operator_registry, run_action
from core.operator.schema import OperatorActionResult, OperatorSafety


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
)


@dataclass
class OperatorExecution:
    result: OperatorActionResult
    answer: str
    record_history: bool = True


class OperatorManager:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self._counter = 0
        self.registry = build_operator_registry()

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

    def _history_answer(self, normalized: str, session_metadata: dict[str, Any]) -> OperatorExecution | None:
        if normalized in {"did you check the repo?", "did you check the repo"}:
            history = get_history(session_metadata)
            if not history:
                # Preserve legacy behavior: allow answer-contract path until any operator action exists.
                return None
            last_repo = latest_action_by_name(session_metadata, "repo_status")
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

        if normalized in {"show the last operator receipt.", "show the last operator receipt"}:
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

        if normalized in {"what operator actions have run?", "what operator actions have run"}:
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

    def _match_action(self, question: str, normalized: str) -> tuple[str, str | None] | None:
        if normalized in {"check the repo.", "check the repo", "what is git status?", "what is git status"}:
            return "repo_status", None
        if normalized in {
            "what branch are we on?",
            "what branch are we on",
            "is the working tree clean?",
            "is the working tree clean",
        }:
            return "repo_status", None
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
            return "docker_compose_ps", None
        if normalized in {
            "what operator tools are available?",
            "what operator tools are available",
            "operator environment",
            "show operator environment",
        }:
            return "operator_environment", None
        if normalized in {"summarize logs.", "summarize logs"}:
            return "logs_summary", None
        if normalized in {"audit memory.", "audit memory"}:
            return "memory_audit", None
        if normalized in {"recent commits", "show recent commits", "repo recent commits"}:
            return "repo_recent_commits", None
        return None

    def _build_answer(self, action_name: str, result: OperatorActionResult) -> str:
        if action_name == "docker_compose_ps" and result.status == "failed":
            return (
                "Container status cannot be proven from inside xv7-core because Docker CLI/socket is unavailable. "
                "No action was run beyond the read-only availability check."
            )
        if result.status == "failed":
            return (
                f"Operator action {result.action_name} failed. "
                f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
            )
        if result.status == "denied":
            return "The requested operator action was denied by read-only safety policy."

        if action_name == "repo_status":
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
            return "Project files (first 20):\n" + "\n".join(f"- {item}" for item in listed)
        if action_name == "read_project_file":
            if result.status == "denied":
                return "Read denied: requested path is outside repo root."
            if result.status == "failed":
                return "File read failed: target file was not found."
            path = str(result.data.get("path", "unknown"))
            content = str(result.data.get("content", "")).strip()
            return f"Read {path}:\n{content}"
        if action_name == "runtime_health":
            health = result.data.get("health", {}) if isinstance(result.data, dict) else {}
            runtime_ok = bool(result.data.get("runtime_status")) if isinstance(result.data, dict) else False
            checked_from = result.data.get("checked_from", "unknown") if isinstance(result.data, dict) else "unknown"
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
            docker_socket_available = bool(result.data.get("docker_socket_available", False))
            return (
                "Operator environment (read-only): "
                f"git_available={git_available}, "
                f"docker_cli_available={docker_cli_available}, "
                f"docker_socket_available={docker_socket_available}."
            )
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
    ) -> OperatorExecution | None:
        metadata = session_metadata or {}
        normalized = self._normalize(question)

        history_answer = self._history_answer(normalized, metadata)
        if history_answer is not None:
            return history_answer

        if (
            any(token in normalized for token in MUTATION_PATTERNS)
            and not self._is_non_mutation_writing_request(normalized)
        ):
            denied = self._denied_result(
                question,
                "B7 is read-only; mutation requests are denied and no action was run.",
            )
            return OperatorExecution(
                result=denied,
                answer=(
                    "B7 is read-only right now. I denied that request and did not run any mutation action."
                ),
                record_history=True,
            )

        matched = self._match_action(question, normalized)
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
