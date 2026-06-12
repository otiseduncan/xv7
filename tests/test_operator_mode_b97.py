from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from core.main import app, memory_manager, operator_manager
from core.operator.schema import OperatorActionResult, OperatorSafety


def _setup_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    operator_manager.repo_root = tmp_path.resolve()
    return TestClient(app)


def _new_session(client: TestClient) -> str:
    response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def _stage(
    client: TestClient,
    session_id: str,
    command_text: str,
    *,
    operator_mode: bool,
) -> dict[str, Any]:
    response = client.post(
        "/operator/stage",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "command_text": command_text,
            "operator_mode": operator_mode,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_normal_mode_mutation_is_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    payload = _stage(client, session_id, "/delete-file test.txt", operator_mode=False)

    assert payload["executed"] is False
    assert payload["pending_action"] is None
    assert payload["receipt"]["status"] == "denied"


def test_operator_mode_stages_then_confirm_executes_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    target = tmp_path / "delete-me.txt"
    target.write_text("hello", encoding="utf-8")

    staged = _stage(client, session_id, f"/delete-file {target}", operator_mode=True)

    assert staged["executed"] is False
    assert staged["pending_action"]["status"] == "pending"
    assert target.exists()
    assert staged["receipt"]["status"] == "pending"

    confirm = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "action_id": staged["pending_action"]["action_id"],
        },
    )
    assert confirm.status_code == 200
    confirmed_payload = confirm.json()
    assert confirmed_payload["receipt"]["status"] == "success"
    assert confirmed_payload["pending_action"] is None
    assert not target.exists()


def test_cancel_staged_mutation_does_not_execute(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    target = tmp_path / "stay.txt"
    target.write_text("keep", encoding="utf-8")

    staged = _stage(client, session_id, f"/delete-file {target}", operator_mode=True)

    cancel = client.post(
        "/operator/cancel",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "action_id": staged["pending_action"]["action_id"],
        },
    )
    assert cancel.status_code == 200
    cancel_payload = cancel.json()
    assert cancel_payload["receipt"]["status"] == "cancelled"
    assert target.exists()


def test_high_risk_requires_typed_confirmation_and_returns_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    staged = _stage(client, session_id, "/git-reset-hard", operator_mode=True)
    action_id = staged["pending_action"]["action_id"]

    wrong = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "action_id": action_id,
            "typed_confirmation": "RESET SOFT",
        },
    )
    assert wrong.status_code == 200
    wrong_payload = wrong.json()
    assert wrong_payload["receipt"]["status"] == "failed"
    assert wrong_payload["pending_action"] is not None

    correct = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "action_id": action_id,
            "typed_confirmation": "RESET HARD",
        },
    )
    assert correct.status_code == 200
    correct_payload = correct.json()
    assert correct_payload["receipt"]["status"] == "not_implemented"
    assert correct_payload["pending_action"] is None


def test_confirm_without_pending_action_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"session_id": session_id, "action_id": "OP-FAKE"},
    )

    assert response.status_code == 400


def test_pending_action_expiry_blocks_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    target = tmp_path / "expire.txt"
    target.write_text("temp", encoding="utf-8")

    staged = _stage(client, session_id, f"/delete-file {target}", operator_mode=True)
    action_id = staged["pending_action"]["action_id"]

    async def _expire_pending() -> None:
        current = await memory_manager.get_session(UUID(session_id))
        pending = current.metadata.get("operator_pending_action", {})
        pending["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        current.metadata["operator_pending_action"] = pending
        await memory_manager.update_session(current)

    asyncio.run(_expire_pending())

    confirm = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"session_id": session_id, "action_id": action_id},
    )
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["receipt"]["status"] == "failed"
    assert (
        "expired" in str(payload["receipt"].get("summary", "")).lower()
        or "expired" in str(payload["answer"]).lower()
    )
    assert target.exists()


def test_read_only_scan_works_without_operator_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    calls: list[str] = []

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        calls.append(action_name)
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name=action_name,
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="test",
            target=str(repo_root),
            stdout_summary="ok",
            stderr_summary="",
            exit_code=0,
            data={"branch": "main", "clean": True, "sync": "in_sync"},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"{action_name} {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    payload = _stage(client, session_id, "/scan-repo", operator_mode=False)
    assert payload["executed"] is True
    assert payload["receipt"]["status"] == "success"
    assert payload["pending_action"] is None

    ports_payload = _stage(client, session_id, "/scan-ports", operator_mode=False)
    assert ports_payload["executed"] is True
    assert ports_payload["receipt"]["status"] == "success"
    assert ports_payload["pending_action"] is None
    assert "scan_ports" in calls


def test_build_task_is_listed_and_requires_operator_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    commands = client.get(
        "/operator/commands",
        headers={"X-XV7-API-Key": "test-secret"},
        params={"operator_mode": True},
    )
    assert commands.status_code == 200
    listed = commands.json().get("commands", [])
    build_task = next((item for item in listed if item.get("slash") == "/build-task"), None)
    assert build_task is not None
    assert build_task.get("mode") == "operator"
    assert build_task.get("enabled") is True

    denied = _stage(
        client,
        session_id,
        "/build-task Implement Code 9 endpoint and tests",
        operator_mode=False,
    )
    assert denied["executed"] is False
    assert denied["pending_action"] is None
    assert denied["receipt"]["status"] == "denied"
    answer = str(denied["answer"]).lower()
    assert "/build-task requires operator mode" in answer
    assert "no files were changed" in answer
    assert "no tests were run" in answer
    assert "no commit or push occurred" in answer


def test_build_task_accepts_natural_language_and_returns_structured_plan_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    files_before = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    payload = _stage(
        client,
        session_id,
        "/build-task Build Code 9 endpoint, add tests, and prepare validation plan",
        operator_mode=True,
    )

    assert payload["executed"] is True
    assert payload["pending_action"] is None
    assert payload["receipt"]["status"] == "success"
    assert payload["receipt"]["read_only"] is True

    answer = str(payload["answer"]).lower()
    assert "build plan" in answer
    assert "task summary:" in answer
    assert "reason:" in answer
    assert "files/directories inspected or recommended for inspection:" in answer
    assert "likely files to change:" in answer
    assert "tests to add/update:" in answer
    assert "validation commands:" in answer
    assert "risk notes:" in answer
    assert "no files were changed. no tests were run. no commit or push occurred." in answer
    assert "next valid operator step:" in answer
    assert (
        "prepare a patch payload" in answer
        or "use vs code/copilot to implement the plan" in answer
    )


def test_build_task_runtime_prompt_is_scope_aware(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    payload = _stage(
        client,
        session_id,
        "/build-task Add runtime endpoint GET /runtime/communication-proof-status returning static Code 8/9 communication proof status JSON. Include backend tests and validation commands. Do not mutate files.",
        operator_mode=True,
    )

    assert payload["executed"] is True
    assert payload["pending_action"] is None
    assert payload["receipt"]["status"] == "success"

    answer = str(payload["answer"]).lower()
    assert "reason: request targets a /runtime http endpoint" in answer
    assert "core/main.py" in answer
    assert "tests/test_runtime_status.py" in answer
    assert "core/operator/actions/test_runner.py" not in answer
    assert "tests/test_operator_test_runner.py" not in answer

    data_preview = payload["receipt"]["data_preview"]
    assert "core/main.py" in data_preview.get("likely_files", [])
    assert "tests/test_runtime_status.py" in data_preview.get("likely_files", [])
    assert "core/operator/actions/test_runner.py" not in data_preview.get(
        "likely_files", []
    )
    assert "tests/test_operator_test_runner.py" not in data_preview.get(
        "likely_files", []
    )
    assert data_preview.get("planning_scope") == "runtime_api"
    assert data_preview.get("validation_commands", [])[:2] == [
        "python -m pytest tests/test_runtime_status.py",
        "python -m pytest",
    ]


def test_build_task_operator_prompt_stays_in_operator_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    payload = _stage(
        client,
        session_id,
        "/build-task Plan a slash command change for operator mode and /apply-patch confirmation flow.",
        operator_mode=True,
    )

    data_preview = payload["receipt"]["data_preview"]
    assert data_preview.get("planning_scope") == "operator_command"
    assert "core/operator/manager.py" in data_preview.get("likely_files", [])
    assert "core/operator/registry.py" in data_preview.get("likely_files", [])
    assert "tests/test_operator_mode_b97.py" in data_preview.get("likely_files", [])
    assert "tests/test_operator_test_runner.py" not in data_preview.get(
        "likely_files", []
    )


def test_build_task_frontend_prompt_stays_in_frontend_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    payload = _stage(
        client,
        session_id,
        "/build-task Update the frontend UI and receipt visibility in public/app.js.",
        operator_mode=True,
    )

    data_preview = payload["receipt"]["data_preview"]
    assert data_preview.get("planning_scope") == "frontend"
    assert "public/app.js" in data_preview.get("likely_files", [])
    assert "public/app.test.js" in data_preview.get("likely_files", [])
    assert "public/app.code8.test.js" in data_preview.get("likely_files", [])
    assert "core/operator/actions/test_runner.py" not in data_preview.get(
        "likely_files", []
    )


def test_build_task_docs_prompt_stays_in_docs_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    files_before = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    payload = _stage(
        client,
        session_id,
        "/build-task Update the documentation and runbook for the new build-task flow.",
        operator_mode=True,
    )

    data_preview = payload["receipt"]["data_preview"]
    assert data_preview.get("planning_scope") == "docs"
    assert any(path.startswith("docs/") for path in data_preview.get("likely_files", []))
    assert "core/operator/actions/test_runner.py" not in data_preview.get(
        "likely_files", []
    )

    files_after = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert files_after == files_before


def test_apply_patch_requires_confirmation_then_executes_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    payload = {
        "approval": {"approved": True, "approval_id": "APP-9A"},
        "source_plan_id": "PLAN-9A",
        "risk": "low",
        "changes": [{"path": "docs/code9a.txt", "content": "ready\n"}],
    }

    staged = _stage(
        client,
        session_id,
        f"/apply-patch {json.dumps(payload, separators=(',', ':'))}",
        operator_mode=True,
    )

    assert staged["executed"] is False
    assert staged["pending_action"] is not None
    assert staged["receipt"]["status"] == "pending"
    assert not (tmp_path / "docs" / "code9a.txt").exists()

    confirm = client.post(
        "/operator/confirm",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "action_id": staged["pending_action"]["action_id"],
        },
    )
    assert confirm.status_code == 200
    confirmed = confirm.json()
    assert confirmed["receipt"]["status"] == "success"
    assert confirmed["pending_action"] is None
    assert (tmp_path / "docs" / "code9a.txt").read_text(encoding="utf-8") == "ready\n"


def test_apply_patch_invalid_payload_fails_safely_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    staged = _stage(client, session_id, "/apply-patch not-json", operator_mode=True)
    assert staged["executed"] is True
    assert staged["pending_action"] is None
    payload = staged
    assert payload["receipt"]["status"] == "failed"
    summary = str(payload["receipt"].get("summary", "")).lower()
    assert "invalid patch payload" in summary


def test_apply_patch_natural_language_is_rejected_at_stage_without_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    stage_payload = _stage(
        client,
        session_id,
        "/apply-patch Enter Operator Mode and build Code 9 endpoint with tests and git push",
        operator_mode=True,
    )

    assert stage_payload["executed"] is True
    assert stage_payload["pending_action"] is None
    assert stage_payload["receipt"]["status"] == "failed"
    summary = str(stage_payload["receipt"].get("summary", ""))
    assert "Invalid patch payload" in summary
    assert "not_implemented" not in str(stage_payload["receipt"]).lower()


def test_run_tests_slash_routes_to_test_runner_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    captured: dict[str, str | None] = {"action_name": None, "target": None}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        captured["action_name"] = action_name
        captured["target"] = target
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name=action_name,
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="test",
            target=str(repo_root),
            stdout_summary="ok",
            stderr_summary="",
            exit_code=0,
            data={"passed": True},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"{action_name} {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    no_arg = _stage(client, session_id, "/run-tests", operator_mode=False)
    assert no_arg["executed"] is True
    assert no_arg["receipt"]["status"] == "success"
    assert captured["action_name"] == "test_runner"
    assert captured["target"] is None

    single_target = _stage(
        client,
        session_id,
        "/run-tests tests/test_operator_registry.py",
        operator_mode=False,
    )
    assert single_target["executed"] is True
    assert single_target["receipt"]["status"] == "success"
    assert captured["action_name"] == "test_runner"
    assert captured["target"] is not None
    forwarded = json.loads(str(captured["target"]))
    assert forwarded["preset"] == "single_pytest"
    assert forwarded["test_target"] == "tests/test_operator_registry.py"
