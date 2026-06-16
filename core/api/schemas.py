from __future__ import annotations

from typing import Any
from uuid import UUID

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


class OperatorStageRequest(BaseModel):
    """Payload for staging a command action."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    command_text: str = Field(min_length=1)
    operator_mode: bool = False


class OperatorConfirmRequest(BaseModel):
    """Payload for confirming a staged command action."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    action_id: str = Field(min_length=1)
    typed_confirmation: str | None = None


class OperatorCancelRequest(BaseModel):
    """Payload for canceling a staged command action."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    action_id: str = Field(min_length=1)


class UpdateFactsRequest(BaseModel):
    """Payload for updating persistent memory facts for a session."""

    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any] = Field(default_factory=dict)


class SetActiveModelProfileRequest(BaseModel):
    """Payload for setting runtime active model profile override."""

    model_config = ConfigDict(extra="forbid")

    profile: str = Field(min_length=1)
    require_available: bool = Field(default=True)
