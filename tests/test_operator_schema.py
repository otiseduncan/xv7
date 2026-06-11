from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from core.operator.schema import OperatorActionResult, OperatorSafety


def _now() -> datetime:
    return datetime.now(UTC)


def test_operator_action_result_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        OperatorActionResult(
            action_id="",
            action_name="repo_status",
            status="success",
            started_at=_now(),
            completed_at=_now(),
            command_or_operation="git status",
            target=".",
            safety=OperatorSafety(allowed=True),
            receipt_label="repo_status OP-1",
        )


def test_operator_action_receipt_format_is_compact() -> None:
    result = OperatorActionResult(
        action_id="OP-20260611-0001",
        action_name="repo_status",
        status="success",
        started_at=_now(),
        completed_at=_now(),
        command_or_operation="git status --porcelain",
        target="X:/XV7/xv7",
        stdout_summary="clean",
        stderr_summary="",
        exit_code=0,
        data={"branch": "main", "clean": True},
        safety=OperatorSafety(allowed=True),
        receipt_label="repo_status OP-20260611-0001",
    )

    receipt = result.receipt()
    assert "Operator receipt:" in receipt
    assert "repo_status OP-20260611-0001 success" in receipt
    assert "read_only=true" in receipt
    assert "exit_code=0" in receipt


def test_operator_safety_defaults_are_non_mutating() -> None:
    safety = OperatorSafety(allowed=True)
    assert safety.read_only is True
    assert safety.mutates_files is False
    assert safety.mutates_git is False
    assert safety.mutates_runtime is False
    assert safety.requires_approval is False
