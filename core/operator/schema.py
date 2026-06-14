from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


OperatorMode = Literal["read_only", "operator", "high_risk"]
OperatorStatus = Literal[
    "success",
    "failed",
    "denied",
    "pending",
    "cancelled",
    "not_implemented",
]


class OperatorSafety(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_only: bool = True
    mutates_files: bool = False
    mutates_git: bool = False
    mutates_runtime: bool = False
    requires_approval: bool = False
    allowed: bool
    denial_reason: str | None = None


class OperatorActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    action_name: str = Field(min_length=1)
    mode: OperatorMode = "read_only"
    status: OperatorStatus
    started_at: datetime
    completed_at: datetime
    command_or_operation: str = Field(min_length=1)
    target: str = Field(min_length=1)
    stdout_summary: str = ""
    stderr_summary: str = ""
    exit_code: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    safety: OperatorSafety
    receipt_label: str = Field(min_length=1)

    def receipt(self) -> str:
        exit_code = self.exit_code if self.exit_code is not None else "n/a"
        return (
            f"Operator receipt: {self.action_name} {self.action_id} {self.status}; "
            f"read_only=true; target={self.target}; exit_code={exit_code}."
        )

    def result_summary(self) -> dict[str, Any]:
        data = dict(self.data)
        status = self._result_status(data)
        changed_files = self._string_list(data.get("changed_files"))
        validation_commands = self._validation_commands(data)
        first_failure = self._first_failure(data)
        local_only_files = self._local_only_files(data)
        candidate_files = self._string_list(data.get("candidate_files"))
        committed_files = self._string_list(data.get("committed_files"))
        skipped_files = self._string_list(data.get("skipped_files"))
        commit_sha = str(data.get("commit_sha") or "")
        pushed = bool(data.get("pushed", False))
        safety_notes = self._safety_notes(data, local_only_files)
        return {
            "action_name": self.action_name,
            "status": status,
            "raw_status": self.status,
            "changed_files": changed_files,
            "candidate_files": candidate_files,
            "committed_files": committed_files,
            "skipped_files": skipped_files,
            "commit_sha": commit_sha,
            "pushed": pushed,
            "validation_commands_run": validation_commands,
            "first_failure": first_failure,
            "safety_notes": safety_notes,
            "commit_push_state": {
                "commit_created": bool(data.get("commit_created", False)),
                "push_performed": bool(data.get("push_performed", False)),
                "requires_separate_approval": True,
            },
            "local_only_files_warning": local_only_files,
        }

    def _result_status(self, data: dict[str, Any]) -> str:
        if (
            self.action_name == "operator_repair_report"
            and self.status == "failed"
            and bool(data.get("patch_required", False))
        ):
            return "needs_patch"
        if self.status == "denied" and self.safety.requires_approval:
            return "needs_approval"
        if self.status == "denied":
            return "blocked"
        if self.status == "success":
            return "passed"
        if self.status == "failed":
            return "failed"
        return str(self.status)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _validation_commands(self, data: dict[str, Any]) -> list[str]:
        for key in (
            "selected_commands",
            "validation_commands_run",
            "validation_commands_rerun",
        ):
            commands = self._string_list(data.get(key))
            if commands:
                return commands
        nested = data.get("validation_before")
        if isinstance(nested, dict):
            preview = nested.get("data_preview")
            if isinstance(preview, dict):
                commands = self._string_list(preview.get("selected_commands"))
                if commands:
                    return commands
        return []

    def _first_failure(self, data: dict[str, Any]) -> str:
        direct = data.get("first_failure_command")
        if direct:
            return str(direct)
        nested = data.get("validation_before")
        if isinstance(nested, dict):
            preview = nested.get("data_preview")
            if isinstance(preview, dict) and preview.get("first_failure_command"):
                return str(preview["first_failure_command"])
        return ""

    def _local_only_files(self, data: dict[str, Any]) -> list[str]:
        local_only = self._string_list(data.get("local_only_files"))
        if local_only:
            return local_only
        protected = self._string_list(data.get("protected_local_only_files"))
        if protected:
            return protected
        nested = data.get("status_before")
        if isinstance(nested, dict):
            preview = nested.get("data_preview")
            if isinstance(preview, dict):
                return self._local_only_files(preview)
        return []

    def _safety_notes(
        self, data: dict[str, Any], local_only_files: list[str]
    ) -> list[str]:
        notes = [
            "No git commit or push was performed.",
            "Commit/push requires separate approval.",
        ]
        if self.safety.requires_approval:
            notes.append("Repo mutation requires explicit approval.")
        if self.safety.denial_reason:
            notes.append(str(self.safety.denial_reason))
        blocked_targets = data.get("blocked_targets")
        if isinstance(blocked_targets, list) and blocked_targets:
            notes.append("One or more requested patch targets were blocked.")
        if local_only_files:
            notes.append(
                "Local-only files are present and protected: "
                + ", ".join(local_only_files)
            )
        return list(dict.fromkeys(note for note in notes if note))

    def structured_receipt(self) -> dict[str, Any]:
        limitation = ""
        if self.stderr_summary:
            lowered = self.stderr_summary.lower()
            if (
                "limitation" in lowered
                or "cannot be proven" in lowered
                or "unavailable" in lowered
            ):
                limitation = self.stderr_summary

        data_preview = dict(self.data)
        if "status_lines" in data_preview and isinstance(
            data_preview["status_lines"], list
        ):
            data_preview["status_lines"] = data_preview["status_lines"][:10]

        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "status": self.status,
            "result_status": self.result_summary()["status"],
            "mode": self.mode,
            "target": self.target,
            "receipt_label": self.receipt_label,
            "read_only": self.safety.read_only,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "exit_code": self.exit_code,
            "safety": self.safety.model_dump(mode="json"),
            "summary": self.stdout_summary or self.stderr_summary,
            "limitation": limitation,
            "data_preview": data_preview,
            "operator_result": self.result_summary(),
        }
