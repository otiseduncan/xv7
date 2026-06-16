from __future__ import annotations

from dataclasses import dataclass

from core.operator.schema import OperatorActionResult


@dataclass
class OperatorExecution:
    result: OperatorActionResult
    answer: str
    record_history: bool = True
