"""Schemas for xv7 runtime session state and short-term memory."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


MessageRole = Literal["system", "user", "assistant"]


class ConversationMessage(BaseModel):
    """Represents one conversation turn in a session.

    Attributes:
        role: Source role of the message.
        content: User-visible content after stripping internal reasoning blocks.
        reasoning_content: Optional hidden reasoning captured from `<|think|>` blocks.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: MessageRole
    content: str = Field(min_length=1)
    reasoning_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reasoning_content")
    @classmethod
    def normalize_reasoning_content(cls, value: str | None) -> str | None:
        """Normalize empty reasoning payloads to None."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SessionState(BaseModel):
    """Tracks active session context and ordered conversation memory."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    session_id: UUID = Field(default_factory=uuid4)
    current_persona: str = Field(default="default", min_length=1)
    context_window_tokens: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[ConversationMessage] = Field(default_factory=list)
