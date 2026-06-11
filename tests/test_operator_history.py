from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.operator.schema import OperatorActionResult, OperatorSafety
from core.runtime.schemas import SessionState


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError(
            "Operator-history tests should be served by operator layer"
        )

    async def aclose(self) -> None:
        return None


async def _fake_query_similar_memories(
    _text: str, limit: int = 3
) -> list[dict[str, str]]:
    return []


async def _fake_persist_vector_memory_round_trip(
    *_args: Any, **_kwargs: Any
) -> dict[str, Any]:
    return {"status": "ok"}


def _setup_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setattr("core.main.base_agent", _FailingAgent())

    memory_store = MemoryStore(records_dir=tmp_path / "memory_records")
    memory_manager = PersistentMemoryManager(store=memory_store)
    memory_manager.bootstrap_seed_records()
    monkeypatch.setattr("core.main.persistent_memory_manager", memory_manager)

    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories", _fake_query_similar_memories
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )
    return TestClient(app)


def _new_session(client: TestClient) -> str:
    response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def test_did_you_check_repo_distinguishes_success_failure_and_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    none_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert none_resp.status_code == 200
    assert (
        "do not have proof of a live repo check"
        in none_resp.json()["messages"][-1]["content"].lower()
    )

    def _run_action_failed(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="repo_status",
            status="failed",
            started_at=now,
            completed_at=now,
            command_or_operation="git status",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary="failure",
            exit_code=1,
            data={},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"repo_status {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_failed)

    attempted = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )
    assert attempted.status_code == 200

    failed_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert failed_resp.status_code == 200
    assert (
        "attempted a repo check, but it failed"
        in failed_resp.json()["messages"][-1]["content"].lower()
    )

    def _run_action_success(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="repo_status",
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="git status",
            target=str(repo_root),
            stdout_summary="ok",
            stderr_summary="",
            exit_code=0,
            data={"branch": "main", "clean": True, "sync": "in_sync"},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"repo_status {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_success)

    successful = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )
    assert successful.status_code == 200

    success_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert success_resp.status_code == 200
    assert (
        "successfully checked the repo"
        in success_resp.json()["messages"][-1]["content"].lower()
    )


def test_what_did_you_just_check_and_last_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    from datetime import UTC, datetime

    def _run_action_runtime(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "runtime_health"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="runtime_health",
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="GET /health",
            target="http://localhost:8000",
            stdout_summary="ok",
            stderr_summary="",
            exit_code=0,
            data={"checked_from": "container"},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"runtime_health {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_runtime)

    run_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Is the runtime healthy?"},
    )
    assert run_resp.status_code == 200

    just_checked = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What did you just check?"},
    )
    assert just_checked.status_code == 200
    assert "runtime_health" in just_checked.json()["messages"][-1]["content"]

    last_receipt = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Show the last operator receipt."},
    )
    assert last_receipt.status_code == 200
    assert (
        "Last operator receipt summary"
        in last_receipt.json()["messages"][-1]["content"]
    )

    history_list = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What operator actions have run?"},
    )
    assert history_list.status_code == 200
    assert "Recent operator actions" in history_list.json()["messages"][-1]["content"]
