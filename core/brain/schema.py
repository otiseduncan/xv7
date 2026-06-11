from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BrainLayer(str, Enum):
    SYSTEM_PROMPT = "system_prompt"
    ACTIVE_FOCUS = "active_focus"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    VERIFIED_STATUS = "verified_status"


class BrainFact(BaseModel):
    """Atomic fact entry in a brain record."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1)
    source_type: Literal[
        "user_stated",
        "inferred",
        "verified_output",
        "user_confirmed",
    ]
    source_detail: str | None = None


class BrainRecord(BaseModel):
    """Canonical persisted brain record schema."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(pattern=r"^XV7-[A-Z]+-\d{4}$")
    layer: BrainLayer
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    body: str = Field(min_length=1)
    status: Literal["active", "archived"] = "active"
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    facts: list[BrainFact] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
