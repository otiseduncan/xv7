from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionResult:
    mode: str
    status: str
    visible_answer: str = ""
    model_used: str | None = None
    fallback_used: bool = False
    runtime_diagnostics: dict[str, Any] = field(default_factory=dict)
    context_receipt: dict[str, Any] = field(default_factory=dict)
    memory_summary: list[str] = field(default_factory=list)
    operator_receipt: dict[str, Any] = field(default_factory=dict)
    artifact_receipt: dict[str, Any] = field(default_factory=dict)
    files_written: list[str] = field(default_factory=list)
    sandbox_decision: str | None = None
    blocked_safety_decision: str | None = None
    next_actions: list[str] = field(default_factory=list)
    result_blocks: list[dict[str, Any]] = field(default_factory=list)
    payload: Any = None
