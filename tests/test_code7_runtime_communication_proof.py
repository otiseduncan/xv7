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
from core.runtime.schemas import SessionState


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("Code 7 communication proof should not hit model inference")

    async def aclose(self) -> None:
        return None


async def _fake_query_similar_memories(
    _text: str, limit: int = 3
) -> list[dict[str, str]]:
    return []


async def _fake_persist_vector_memory_round_trip(
    *_args: Any, **_kwargs: Any
) -> dict[str, Any]:
    return {"status": "ok", "stored_at": datetime.now(UTC).isoformat()}


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


def _post_message(client: TestClient, session_id: str, raw_text: str) -> dict[str, Any]:
    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": raw_text},
    )
    assert response.status_code == 200
    return response.json()


def _latest_text(payload: dict[str, Any]) -> str:
    return str(payload["messages"][-1]["content"])


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata", {})
    assert isinstance(metadata, dict)
    return metadata


def _provenance(payload: dict[str, Any]) -> dict[str, Any]:
    provenance = _metadata(payload).get("answer_provenance", {})
    assert isinstance(provenance, dict)
    return provenance


def _assert_policy_only(payload: dict[str, Any]) -> None:
    provenance = _provenance(payload)
    assert provenance.get("runtime_model_inference_proven") is False
    assert provenance.get("answer_source") != "runtime_model_inference"

    assistant_payload = _metadata(payload).get("last_assistant_payload", {})
    assert isinstance(assistant_payload, dict)
    assert assistant_payload.get("model_use_receipt") in ({}, None)


def _receipt_record_ids(payload: dict[str, Any]) -> list[str]:
    receipt = _metadata(payload).get("context_receipt", {})
    assert isinstance(receipt, dict)
    return [str(item) for item in receipt.get("record_ids", [])]


def test_code7_active_focus_live_api_contract_is_policy_only_and_persistent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    focus_text = (
        "correct communication with operator Otis, learning his workflows, "
        "and reducing hallucinations with proof-first answers"
    )
    set_focus = _post_message(
        client,
        session_id,
        f"change your active focus to {focus_text}",
    )

    answer = _latest_text(set_focus).lower()
    assert "updating active focus" in answer
    assert "model:" not in answer
    assert "qwen" not in answer
    _assert_policy_only(set_focus)

    metadata = _metadata(set_focus)
    active_focus = metadata.get("active_focus", {})
    assert isinstance(active_focus, dict)
    focus_id = str(active_focus.get("id", ""))
    assert focus_id.startswith("XV7-FOCUS-")
    assert active_focus.get("source") == "direct_user_instruction"
    assert active_focus.get("persistence") == "brain_record_saved"
    assert active_focus.get("session_fact_saved") is True

    provenance = _provenance(set_focus)
    assert provenance.get("policy_source") == "active_focus_intent"
    assert provenance.get("brain_answer_source") == "active_focus_update"
    assert provenance.get("intent_class") == "active_focus_update"
    assert provenance.get("action") == "create_active_focus_record"
    assert provenance.get("protected") is False

    context_receipt = metadata.get("context_receipt", {})
    assert isinstance(context_receipt, dict)
    assert focus_id in context_receipt.get("record_ids", [])
    receipt_items = context_receipt.get("context_receipts", [])
    assert receipt_items
    first_receipt = receipt_items[0]
    assert first_receipt.get("layer") == "active_focus"
    assert first_receipt.get("record_id") == focus_id
    assert first_receipt.get("persistence") == "brain_record_saved"

    same_session = _post_message(
        client,
        session_id,
        "what did I just change your focus to?",
    )
    same_text = _latest_text(same_session).lower()
    assert "active focus" in same_text
    assert "communication" in same_text
    assert "operator" in same_text or "otis" in same_text
    _assert_policy_only(same_session)
    assert focus_id in _receipt_record_ids(same_session)

    new_session_id = _new_session(client)
    fresh_session = _post_message(
        client,
        new_session_id,
        "what is your current active focus",
    )
    fresh_text = _latest_text(fresh_session).lower()
    assert "communication" in fresh_text
    assert "workflow" in fresh_text or "proof" in fresh_text
    _assert_policy_only(fresh_session)
    assert focus_id in _receipt_record_ids(fresh_session)

    guided = _post_message(
        client,
        new_session_id,
        "so what are the next steps that we need to pursue an increasing fluid communication",
    )
    guided_text = _latest_text(guided).lower()
    assert "track otis corrections" in guided_text
    assert "save communication preferences" in guided_text
    assert "learn workflow habits" in guided_text
    assert "compact receipts" in guided_text
    assert "source/proof" in guided_text
    assert "local scan" not in guided_text
    assert "without explicit tool access" not in guided_text

    guided_metadata = _metadata(guided)
    assert guided_metadata.get("active_focus_id") == focus_id
    assert guided_metadata.get("focus_applied") is True
    assert guided_metadata.get("response_mode") == "active_focus_guided"
    assert guided_metadata.get("model_used") == "policy_only"
    assert guided_metadata.get("fallback_used") is False
    assert focus_id in guided_metadata.get("source_record_ids", [])
    assert focus_id in _receipt_record_ids(guided)

    records_response = client.get(
        "/runtime/brain/records",
        params={"layer": "active_focus", "include_archived": "false"},
    )
    assert records_response.status_code == 200
    records_payload = records_response.json()
    records = records_payload.get("records", [])
    assert isinstance(records, list)
    assert any(
        isinstance(record, dict)
        and record.get("record_id") == focus_id
        and record.get("status") == "active"
        for record in records
    )


def test_code7_active_focus_update_fails_hard_when_runtime_store_is_unwritable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)

    source_brain_dir = Path("data/brain/records")
    seed_dir = tmp_path / "blocked_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    for path in source_brain_dir.glob("*.json"):
        shutil.copy2(path, seed_dir / path.name)

    runtime_file = tmp_path / "not_a_directory"
    runtime_file.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(
        "core.main.brain_context_manager",
        BrainContextManager(records_dir=seed_dir, runtime_records_dir=runtime_file),
    )

    session_id = _new_session(client)
    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change your active focus to correct communication with operator Otis and proof-first answers",
        },
    )

    assert response.status_code == 500
    detail = str(response.json().get("detail", "")).lower()
    assert "runtime record store" in detail
    assert "not a directory" in detail
