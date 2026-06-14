from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pytest

from core.operator.actions import repair_report as repair_module
from core.operator.actions.repair_report import operator_repair_report
from core.operator.registry import run_action
from core.operator.schema import OperatorActionResult, OperatorSafety


APPROVAL = {"approved": True, "approval_id": "APP-REPAIR-1"}


def _action_result(
    *,
    action_id: str,
    action_name: str,
    status: str,
    data: dict[str, Any],
    stderr: str = "",
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        mode="read_only",
        status=status,  # type: ignore[arg-type]
        started_at=now,
        completed_at=now,
        command_or_operation=f"fake {action_name}",
        target="fake",
        stdout_summary="fake",
        stderr_summary=stderr,
        exit_code=0 if status == "success" else 1,
        data=data | {"commit_created": False, "push_performed": False},
        safety=OperatorSafety(allowed=True),
        receipt_label=f"{action_name} {action_id}",
    )


def _status(action_id: str, repo_root: Path) -> OperatorActionResult:
    return _action_result(
        action_id=action_id,
        action_name="operator_status_report",
        status="success",
        data={
            "repo_root": str(repo_root),
            "changed_files": [],
            "commit_created": False,
            "push_performed": False,
        },
    )


def _validation(
    *,
    action_id: str,
    passed: bool,
    command: str = "python -m ruff check core tests scripts",
) -> OperatorActionResult:
    first_failure = None
    if not passed:
        first_failure = {
            "command": command,
            "exit_code": 1,
            "passed": False,
            "stderr_tail": "lint failed",
        }
    return _action_result(
        action_id=action_id,
        action_name="operator_validation_report",
        status="success" if passed else "failed",
        stderr="" if passed else f"First validation failure: {command}",
        data={
            "profile": "python-core",
            "selected_commands": [command],
            "passed": passed,
            "first_failure": first_failure,
            "first_failure_command": command if not passed else None,
        },
    )


def test_repair_report_validation_pass_no_patch_does_not_mutate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("same\n", encoding="utf-8")
    monkeypatch.setattr(repair_module, "operator_status_report", _status)
    monkeypatch.setattr(
        repair_module,
        "operator_validation_report",
        lambda **kwargs: _validation(action_id=kwargs["action_id"], passed=True),
    )

    result = operator_repair_report(
        action_id="OP-REPAIR-1",
        repo_root=tmp_path,
        request={},
    )

    assert result.status == "success"
    assert result.data["max_cycles"] == 1
    assert result.data["repair_fixed_failure"] is True
    assert result.data["patch_apply"] is None
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert marker.read_text(encoding="utf-8") == "same\n"


def test_repair_report_validation_failure_without_patch_reports_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(repair_module, "operator_status_report", _status)
    monkeypatch.setattr(
        repair_module,
        "operator_validation_report",
        lambda **kwargs: _validation(action_id=kwargs["action_id"], passed=False),
    )

    result = operator_repair_report(
        action_id="OP-REPAIR-2",
        repo_root=tmp_path,
        request={},
    )

    assert result.status == "failed"
    assert result.data["patch_required"] is True
    assert result.data["first_failure_command"] == (
        "python -m ruff check core tests scripts"
    )
    assert "concrete patch required" in result.stdout_summary
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_repair_report_approved_patch_applies_and_reruns_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "core" / "demo.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    validations: list[bool] = [False, True]
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(repair_module, "operator_status_report", _status)

    def _fake_validation(**kwargs: Any) -> OperatorActionResult:
        calls.append(kwargs)
        return _validation(
            action_id=kwargs["action_id"],
            passed=validations.pop(0),
        )

    monkeypatch.setattr(repair_module, "operator_validation_report", _fake_validation)

    result = operator_repair_report(
        action_id="OP-REPAIR-3",
        repo_root=tmp_path,
        request={
            "approval": APPROVAL,
            "patch": {
                "changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}],
            },
        },
    )

    assert result.status == "success"
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert result.data["changed_files"] == ["core/demo.py"]
    assert result.data["repair_fixed_failure"] is True
    assert calls[1]["commands"] == ["python -m ruff check core tests scripts"]
    assert result.data["validation_commands_rerun"] == [
        "python -m ruff check core tests scripts"
    ]
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_repair_report_unapproved_repo_patch_does_not_mutate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "core" / "demo.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(repair_module, "operator_status_report", _status)
    monkeypatch.setattr(
        repair_module,
        "operator_validation_report",
        lambda **kwargs: _validation(action_id=kwargs["action_id"], passed=False),
    )

    result = operator_repair_report(
        action_id="OP-REPAIR-4",
        repo_root=tmp_path,
        request={
            "patch": {
                "changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}],
            },
        },
    )

    assert result.status == "denied"
    assert "approval is required" in result.stderr_summary
    assert result.data["patch_preview"]["status"] == "success"
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_repair_report_safety_block_stops_repair_and_preserves_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(repair_module, "operator_status_report", _status)
    monkeypatch.setattr(
        repair_module,
        "operator_validation_report",
        lambda **kwargs: _validation(action_id=kwargs["action_id"], passed=False),
    )

    result = operator_repair_report(
        action_id="OP-REPAIR-5",
        repo_root=tmp_path,
        request={
            "approval": APPROVAL,
            "patch": {
                "changes": [{"path": "docker-compose.yml", "content": "bad: true\n"}],
            },
        },
    )

    assert result.status == "denied"
    assert "protected local-only" in result.stderr_summary
    assert compose.read_text(encoding="utf-8") == "services: {}\n"
    assert result.data["patch_apply"] is None
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_repair_report_registry_route_and_max_cycle_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(repair_module, "operator_status_report", _status)
    monkeypatch.setattr(
        repair_module,
        "operator_validation_report",
        lambda **kwargs: _validation(action_id=kwargs["action_id"], passed=True),
    )

    result = run_action(
        "operator_repair_report",
        action_id="OP-REPAIR-6",
        repo_root=tmp_path,
        target=json.dumps({"profile": "python-core"}),
    )

    assert result.status == "success"
    assert result.action_name == "operator_repair_report"
    assert result.data["max_cycles"] == 1
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
