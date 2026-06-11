from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
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
