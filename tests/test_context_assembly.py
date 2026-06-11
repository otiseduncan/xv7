from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from core.brain.manager import BrainContextManager
from core.main import app
from core.runtime.schemas import SessionState


def test_active_context_compact_receipt_has_required_layers() -> None:
    manager = BrainContextManager()
    context = manager.build_active_context()
    compact = str(context.receipt.get("compact", ""))
    structured = context.receipt.get("context_receipts", [])

    assert "System Prompt XV7-SYSTEM-0001" in compact
    assert "Active Focus XV7-FOCUS-0004" in compact
    assert "Verified Status XV7-VERIFIED-0001" in compact
    assert isinstance(structured, list)
    assert all(isinstance(item, dict) for item in structured)
    assert all(
        "layer" in item and "record_id" in item
        for item in structured
        if isinstance(item, dict)
    )


def test_missing_record_reports_missing_in_answer(monkeypatch, tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    source = Path("data/brain/records/XV7-SYSTEM-0001.json")
    (records_dir / source.name).write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    monkeypatch.setenv("XV7_BRAIN_RECORDS_PATH", str(records_dir))

    manager = BrainContextManager(records_dir=records_dir)
    answer = manager.answer_from_records("What are we working on?")
    scoped_context = manager.build_context_for_question("What are we working on?")

    assert answer == "Missing required record: active_focus."
    assert scoped_context.receipt["compact"] == "Context receipt: Active Focus missing."


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("B4 pass questions should be answered from brain records")

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


def test_b4_pass_questions_answer_from_records_with_compact_receipt(
    monkeypatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setattr("core.main.base_agent", _FailingAgent())
    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )

    client = TestClient(app)
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["session_id"]

    cases = [
        (
            "Who are you?",
            "I am Xoduz",
            "System Prompt XV7-SYSTEM-0001",
            "system_prompt",
            ["Active Focus", "Memory", "Verified Status"],
        ),
        (
            "What are we working on?",
            "B9.8",
            "Active Focus XV7-FOCUS-0004",
            "active_focus",
            ["System Prompt", "Knowledge", "Memory", "Verified Status"],
        ),
        (
            "What do you know is verified?",
            "Verified facts:",
            "Verified Status XV7-VERIFIED-0001",
            "verified_status",
            ["System Prompt", "Active Focus", "Knowledge", "Memory"],
        ),
        (
            "What repo/status are we on?",
            "Repo/status:",
            "Verified Status XV7-VERIFIED-0001",
            "verified_status",
            ["System Prompt", "Active Focus", "Knowledge", "Memory"],
        ),
    ]

    for (
        question,
        expected,
        required_receipt_fragment,
        expected_layer,
        unexpected_layer_labels,
    ) in cases:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": question},
        )
        assert response.status_code == 200

        payload = response.json()
        answer = payload["messages"][-1]["content"]
        assert expected in answer
        assert "Context receipt:" not in answer
        for disallowed in unexpected_layer_labels:
            assert disallowed not in answer

        context_receipt = payload["metadata"].get("context_receipt", {})
        assert "record_ids" in context_receipt
        assert len(context_receipt["record_ids"]) >= 1
        assert required_receipt_fragment.split()[-1] in context_receipt.get(
            "record_ids", []
        )
        structured = context_receipt.get("context_receipts", [])
        assert isinstance(structured, list)
        assert len(structured) >= 1
        assert structured[0].get("layer") == expected_layer


def test_runtime_active_context_endpoint_returns_prompt_and_receipt() -> None:
    client = TestClient(app)
    response = client.get("/runtime/context/active")

    assert response.status_code == 200
    payload = response.json()
    assert "prompt" in payload
    assert "receipt" in payload
    assert "compact_receipt" in payload
    assert "XV7-SYSTEM-0001" in payload["compact_receipt"]
