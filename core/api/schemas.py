from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.brain.schema import BrainLayer


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


class BrainRecordUpdateRequest(BaseModel):
    """Payload for runtime brain record edits stored as runtime overrides."""

    model_config = ConfigDict(extra="forbid")

    layer: BrainLayer | None = None
    title: str | None = Field(default=None, min_length=1)
    body: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    status: Literal["active", "pending", "pending_review", "disabled", "archived"] | None = None
    relevance_state: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ] | None = None
    superseded_by: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    applies_when: str | None = None
    review_reason: str | None = None
    last_reviewed_at: str | None = None


class BrainRecordRelevanceUpdateRequest(BaseModel):
    """Payload for setting brain record relevance lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    relevance_state: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ]
    superseded_by: str | None = None
    review_reason: str | None = None
    applies_when: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


class BrainRecordApplyRecommendationRequest(BaseModel):
    """Explicit approval payload for a staged hygiene recommendation."""

    model_config = ConfigDict(extra="forbid")

    recommendation_type: Literal[
        "mark_historical_via_runtime_override",
        "split_record",
    ]
    approve: bool = True
    operational_title: str | None = None
    operational_summary: str | None = None
    operational_body: str | None = None
    tags: list[str] | None = None
    layer: BrainLayer | None = None


class BrainRecordSplitRequest(BaseModel):
    """Payload for explicitly splitting mixed historical/current records."""

    model_config = ConfigDict(extra="forbid")

    operational_title: str | None = None
    operational_summary: str | None = None
    operational_body: str | None = None
    tags: list[str] | None = None
    layer: BrainLayer | None = None
    review_reason: str | None = None
    applies_when: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
