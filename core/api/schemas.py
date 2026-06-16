from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionRequest(BaseModel):
    """Optional initialization payload for a new session."""

    model_config = ConfigDict(extra="forbid")

    current_persona: str = Field(default="default", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddMessageRequest(BaseModel):
    """Payload for appending a new user message and running inference."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1)
    operator_mode: bool = False
