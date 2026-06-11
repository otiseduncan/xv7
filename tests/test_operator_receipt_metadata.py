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
            "Operator metadata tests should not reach runtime model path"
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


def _result(
    action_name: str, status: str, action_id: str, target: str
) -> OperatorActionResult:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        status=status,
        started_at=now,
        completed_at=now,
        command_or_operation="test operation",
        target=target,
        stdout_summary="summary",
        stderr_summary="",
        exit_code=0 if status == "success" else 1,
        data={"branch": "main", "clean": True, "status_lines": []},
        safety=OperatorSafety(allowed=status != "denied"),
        receipt_label=f"{action_name} {action_id}",
    )


def test_operator_receipt_metadata_attached_to_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_success(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        return _result("repo_status", "success", action_id, str(repo_root))

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_success)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )
    assert response.status_code == 200

    payload = response.json()
    assistant = payload["messages"][-1]
    metadata = assistant.get("metadata", {})
    assert metadata.get("visible_text")
    assert isinstance(metadata.get("operator_receipts"), list)
    receipt = metadata["operator_receipts"][0]
    for key in (
        "action_id",
        "action_name",
        "status",
        "mode",
        "target",
        "receipt_label",
        "read_only",
        "started_at",
        "completed_at",
        "exit_code",
        "safety",
        "summary",
        "limitation",
        "data_preview",
    ):
        assert key in receipt


def test_session_history_records_success_failed_and_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_failed(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        return _result("repo_status", "failed", action_id, str(repo_root))

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_failed)

    failed_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )
    assert failed_resp.status_code == 200

    denied_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Delete a file."},
    )
    assert denied_resp.status_code == 200

    history = denied_resp.json().get("metadata", {}).get("operator_action_history", [])
    assert isinstance(history, list)
    assert any(
        item.get("status") == "failed" for item in history if isinstance(item, dict)
    )
    assert any(
        item.get("status") == "denied" for item in history if isinstance(item, dict)
    )
