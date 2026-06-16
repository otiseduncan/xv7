from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from core.main import app
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.runtime.schemas import SessionState
from core.prompts.commercial_style import build_commercial_system_prompt


class _CaptureAgent:
    personas = {"default": {"name": "default"}}

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def generate_response(
        self, session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        self.messages = [
            {"role": message.role, "content": message.content}
            for message in session_state.messages
        ]
        return (
            "Use the failing assertion, isolate the smallest repro, then rerun the targeted test.",
            {
                "model_profile": "test",
                "profile_source": "test",
                "runtime_role": "chat",
                "model_tag": "fake-commercial-model",
                "model_selection_source": "test",
                "request_id": "commercial-prompt-test",
            },
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


def _client_with_capture_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[TestClient, _CaptureAgent]:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
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
    capture_agent = _CaptureAgent()
    monkeypatch.setattr("core.main.base_agent", capture_agent)
    return TestClient(app), capture_agent


def test_commercial_prompt_builder_sets_reliable_answer_contract() -> None:
    prompt = build_commercial_system_prompt(
        active_focus="stabilize XV7 communication",
        learned_rules=["Do not claim tests passed unless they were run."],
        session_facts={"project": "xv7"},
    )

    lowered = prompt.lower()
    assert "commercial response baseline" in lowered
    assert "answer the user's actual request first" in lowered
    assert "do not expose hidden chain-of-thought" in lowered
    assert "never invent a current date" in lowered
    assert "stabilize xv7 communication" in lowered
    assert "do not claim tests passed unless they were run" in lowered


def test_model_fallback_receives_commercial_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client, capture_agent = _client_with_capture_agent(monkeypatch, tmp_path)
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What is the best way to debug a failing unit test?"},
    )

    assert response.status_code == 200
    system_prompts = [
        message["content"]
        for message in capture_agent.messages
        if message["role"] == "system"
    ]
    joined = "\n".join(system_prompts).lower()
    assert "commercial response baseline" in joined
    assert "answer the user's actual request first" in joined
    assert "do not expose hidden chain-of-thought" in joined
    assert "runtime clock" in joined
    assert (
        response.json()["metadata"]["answer_provenance"]["answer_source"]
        == "runtime_model_inference"
    )
