from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil
from typing import Any

from fastapi.testclient import TestClient
import pytest

from core.brain.manager import BrainContextManager
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
        raise AssertionError("B7 prompts should not hit model inference in these tests")

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


def _result(
    *, action_name: str, status: str, action_id: str, stderr_summary: str = ""
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        status=status,
        started_at=now,
        completed_at=now,
        command_or_operation="test operation",
        target="X:/XV7/xv7",
        stdout_summary="",
        stderr_summary=stderr_summary,
        exit_code=0 if status == "success" else 1,
        data={"branch": "main", "clean": True},
        safety=OperatorSafety(allowed=status != "denied"),
        receipt_label=f"{action_name} {action_id}",
    )


def _setup_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setattr("core.main.base_agent", _FailingAgent())

    memory_store = MemoryStore(records_dir=tmp_path / "memory_records")
    memory_manager = PersistentMemoryManager(store=memory_store)
    memory_manager.bootstrap_seed_records()
    monkeypatch.setattr("core.main.persistent_memory_manager", memory_manager)

    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )

    source_brain_dir = Path("data/brain/records")
    test_brain_dir = tmp_path / "brain_seed_records"
    test_runtime_brain_dir = tmp_path / "brain_runtime_records"
    test_brain_dir.mkdir(parents=True, exist_ok=True)
    test_runtime_brain_dir.mkdir(parents=True, exist_ok=True)
    for path in source_brain_dir.glob("*.json"):
        shutil.copy2(path, test_brain_dir / path.name)

    monkeypatch.setenv("XV7_BRAIN_RECORDS_PATH", str(test_brain_dir))
    monkeypatch.setenv("XV7_BRAIN_RUNTIME_RECORDS_PATH", str(test_runtime_brain_dir))
    monkeypatch.setattr(
        "core.main.brain_context_manager",
        BrainContextManager(
            records_dir=test_brain_dir,
            runtime_records_dir=test_runtime_brain_dir,
        ),
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





























































__all__ = [name for name in globals() if not name.startswith("__")]
