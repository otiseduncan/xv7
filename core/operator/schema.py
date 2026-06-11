from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    mode: Literal["read_only", "operator", "high_risk"] = "read_only"
    status: Literal["success", "failed", "denied", "pending", "cancelled", "not_implemented"]
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

    def structured_receipt(self) -> dict[str, Any]:
        limitation = ""
        if self.stderr_summary:
            lowered = self.stderr_summary.lower()
            if "limitation" in lowered or "cannot be proven" in lowered or "unavailable" in lowered:
                limitation = self.stderr_summary

        data_preview = dict(self.data)
        if "status_lines" in data_preview and isinstance(data_preview["status_lines"], list):
            data_preview["status_lines"] = data_preview["status_lines"][:10]

        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "status": self.status,
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
        }
