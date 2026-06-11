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
    mode: Literal["read_only"] = "read_only"
    status: Literal["success", "failed", "denied"]
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
