from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.kernel.request_context import RequestContext


@dataclass(frozen=True)
class ExecutionPlan:
    mode: str
    executor: str
    request_context: RequestContext
    selected_model_path: str | None = None
    selected_model_tag: str | None = None
    safety_decision: str = "allowed"
    expected_result_shape: str = "session_state"
    receipt_requirements: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
