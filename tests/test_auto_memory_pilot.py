from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.brain.manager import BrainContextManager
from core.main import app
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.runtime.schemas import SessionState


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("Auto-memory tests should not reach model inference")

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


def _setup_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, PersistentMemoryManager]:
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

    monkeypatch.setattr(
        "core.main.brain_context_manager",
        BrainContextManager(),
    )

    return TestClient(app), memory_manager


def _new_session(client: TestClient) -> str:
    response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


@pytest.mark.parametrize(
    "prompt,expected_type,expected_phrase",
    [
        (
            "I don't want long proof dumps unless I ask.",
            "answer_style_preference",
            "Got it",
        ),
        (
            "When I say generate website, I mean preview first.",
            "workflow_habit",
            "Got it",
        ),
    ],
)
def test_auto_memory_saves_preferences_and_habits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    expected_type: str,
    expected_phrase: str,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert expected_phrase.lower() in answer.lower()

    active = manager.list_active_memories()
    assert any(record.memory_type == expected_type for record in active)


def test_workflow_habit_routes_website_prompt_to_preview_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    habit_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "When I say generate website, I mean preview first."},
    )
    assert habit_response.status_code == 200

    site_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Generate a website for Harry's Hot Dog Cart."},
    )

    assert site_response.status_code == 200
    payload = site_response.json()
    answer = payload["messages"][-1]["content"].lower()
    metadata = payload.get("metadata", {})
    assert "built" in answer and "sandbox" in answer
    assert metadata.get("answer_provenance", {}).get("artifact_generation") == "sandbox_build"
    assert metadata.get("auto_memory_record_ids")
    assert any(record.memory_type == "workflow_habit" for record in manager.list_active_memories())


def test_unclear_emotional_feedback_requests_clarification_and_does_not_save(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    before_ids = {record.id for record in manager.list_active_memories()}

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "No, that is wrong."},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "tell me the exact behavior" in answer
    after_ids = {record.id for record in manager.list_active_memories()}
    assert before_ids == after_ids


def test_proof_guard_saves_hallucination_proof_preference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Don't guess; verify repo status first."},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "keep that preference going forward" in answer

    active = manager.list_active_memories()
    assert any(
        "verify repo status first" in record.content.lower() for record in active
    )


def test_ci_green_refuses_without_proof(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, _manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Is CI green?"},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "require proof before claiming ci/github status" in answer


def test_duplicate_preferences_strengthen_existing_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompt = "I don't want long proof dumps unless I ask."
    first = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )
    assert first.status_code == 200
    first_records = [
        record for record in manager.list_active_memories() if record.memory_type == "answer_style_preference"
    ]
    assert len(first_records) == 1
    first_id = first_records[0].id

    second = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )
    assert second.status_code == 200
    second_records = [
        record for record in manager.list_active_memories() if record.memory_type == "answer_style_preference"
    ]
    assert len(second_records) == 1
    assert second_records[0].id == first_id


def test_fresh_session_retrieves_saved_preferences_silently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    first_session = _new_session(client)
    response = client.post(
        f"/sessions/{first_session}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "I don't want long proof dumps unless I ask."},
    )
    assert response.status_code == 200
    saved = next(
        record
        for record in manager.list_active_memories()
        if record.memory_type == "answer_style_preference"
    )

    second_session = _new_session(client)
    follow_up = client.post(
        f"/sessions/{second_session}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Generate a website for Harry's Hot Dog Cart."},
    )
    assert follow_up.status_code == 200
    metadata = follow_up.json().get("metadata", {})
    assert saved.id in metadata.get("auto_memory_record_ids", [])
    assert "auto_memory_context_prompt" in metadata


def test_runtime_restart_loads_saved_auto_memories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, manager = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "I don't want long proof dumps unless I ask."},
    )
    assert response.status_code == 200

    restarted = PersistentMemoryManager(store=manager.store)
    restarted_active = restarted.list_active_memories()
    assert any(
        record.memory_type == "answer_style_preference" for record in restarted_active
    )
