from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RequestContext:
    raw_user_message: str
    normalized_message: str
    session_id: UUID
    user_id: str | None = None
    auth_context: dict[str, Any] | None = None
    operator_mode_enabled: bool = False
    source_channel: str = "session_message"
    request_metadata: dict[str, Any] = field(default_factory=dict)
    session_metadata: dict[str, Any] = field(default_factory=dict)
    session_messages: list[dict[str, Any]] = field(default_factory=list)
