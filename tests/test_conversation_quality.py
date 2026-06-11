from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from core.brain.manager import BrainContextManager
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.main import app
from core.runtime.schemas import SessionState


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("These prompts should be handled by answer contract")

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


def _setup_contract_only(monkeypatch, tmp_path: Path) -> TestClient:
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
    return TestClient(app)


def _new_session(client: TestClient) -> str:
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201
    return session_response.json()["session_id"]


def test_missing_memory_answer_is_honest(monkeypatch, tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "XV7-SYSTEM-0001.json",
        "XV7-FOCUS-0001.json",
        "XV7-KNOWLEDGE-0001.json",
        "XV7-VERIFIED-0001.json",
    ):
        source = Path("data/brain/records") / name
        (records_dir / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("XV7_BRAIN_RECORDS_PATH", str(records_dir))
    manager = BrainContextManager(records_dir=records_dir)
    answer = manager.answer_from_records("What do you remember?", session_metadata={})
    assert answer == "Missing required record: memory."


def test_verified_facts_answer_uses_verified_status_only(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you know is verified?"},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "Verified facts:" in answer
    assert "Context receipt: Verified Status XV7-VERIFIED-0001." in answer
    assert "System Prompt" not in answer


def test_every_contract_answer_has_compact_receipt(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompts = [
        "Are we beta ready?",
        "Did you check the repo?",
        "What failed?",
        "What do you remember?",
        "Make a guess about what is next.",
        "What model are you using?",
    ]

    for prompt in prompts:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        answer = response.json()["messages"][-1]["content"]
        assert "Context receipt:" in answer


def test_model_question_requires_proof_in_chat_path(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What model are you using?"},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"]
    assert "Context receipt:" in answer
    assert "brain/policy layer" in answer
    assert "xv7-brain-records" not in answer

    metadata = payload.get("metadata", {})
    provenance = metadata.get("answer_provenance", {})
    assert provenance.get("answer_source") == "brain_policy"
    assert provenance.get("policy_source") == "answer_contract"
    assert provenance.get("runtime_model_inference_proven") is False


def test_memory_recall_uses_memory_records_only(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you remember?"},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "Remembered items (Memory records only):" in answer
    assert "Verified facts:" not in answer
    assert "Knowledge facts:" not in answer
    assert "Context receipt: Memory" in answer


def test_verified_vs_remembered_separation_in_chat_path(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    remember = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you remember about XV7?"},
    )
    assert remember.status_code == 200

    separation = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Is that verified or just remembered?"},
    )
    assert separation.status_code == 200
    answer = separation.json()["messages"][-1]["content"]
    assert "not verified status" in answer
    assert "Context receipt: Memory" in answer


def test_forget_that_is_ambiguous_does_not_delete(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    created_a = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Remember this: Otis wants receipts to stay compact."},
    )
    created_b = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Remember this: Otis wants receipt memory to include ids."},
    )
    assert created_a.status_code == 200
    assert created_b.status_code == 200

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Forget that receipt memory."},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "matches multiple memories" in answer


def test_structured_context_receipt_has_layer_by_prompt(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    cases = [
        ("What is my name?", "memory"),
        ("What are we working on right now?", "active_focus"),
        ("Can you help write implementation prompts for VS Code/Copilot?", "knowledge"),
        ("What do you know is verified?", "verified_status"),
        ("What is your name?", "system_prompt"),
    ]

    for prompt, expected_layer in cases:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200

        metadata = response.json().get("metadata", {})
        context_receipt = metadata.get("context_receipt", {})
        structured = context_receipt.get("context_receipts", [])
        assert isinstance(structured, list)
        assert len(structured) >= 1
        assert structured[0].get("layer") == expected_layer
