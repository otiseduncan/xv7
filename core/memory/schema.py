from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MemoryStatus = Literal["active", "inactive", "superseded", "deleted"]
MemoryType = Literal[
    "user_preference",
    "project_preference",
    "project_fact",
    "workflow_note",
    "answer_style_preference",
    "communication_preference",
    "workflow_habit",
    "user_correction",
    "active_focus_candidate",
    "verified_status_candidate",
    "temporary_context",
    "emotional_feedback_unclear",
    "correction",
    "reminder_candidate",
]
MemorySource = Literal[
    "user_explicit",
    "assistant_observed",
    "operator_approved",
    "imported_reference",
]


class MemoryRecord(BaseModel):
    """Durable XV7 persistent memory record."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^XV7-MEMORY-\d{4}$")
    layer: Literal["memory"] = "memory"
    status: MemoryStatus = "inactive"
    memory_type: MemoryType
    content: str = Field(min_length=1)
    source: MemorySource
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime
    supersedes: str | None = None
    tags: list[str] = Field(default_factory=list)
    receipt_label: str = Field(min_length=1)
    pending_approval: bool = False
