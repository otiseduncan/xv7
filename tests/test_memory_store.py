from __future__ import annotations

from pathlib import Path

from core.memory.schema import MemoryRecord
from core.memory.store import MemoryStore


def test_memory_record_validation_requires_expected_fields() -> None:
    payload = {
        "id": "XV7-MEMORY-0099",
        "layer": "memory",
        "status": "active",
        "memory_type": "user_preference",
        "content": "Otis prefers concise updates.",
        "source": "user_explicit",
        "confidence": 0.9,
        "created_at": "2026-06-11T00:00:00Z",
        "updated_at": "2026-06-11T00:00:00Z",
        "supersedes": None,
        "tags": ["otis"],
        "receipt_label": "Memory XV7-MEMORY-0099",
        "pending_approval": False,
    }
    record = MemoryRecord.model_validate(payload)
    assert record.id == "XV7-MEMORY-0099"


def test_memory_store_round_trip_and_next_id(tmp_path: Path) -> None:
    store = MemoryStore(records_dir=tmp_path / "records")
    record = MemoryRecord.model_validate(
        {
            "id": "XV7-MEMORY-0003",
            "layer": "memory",
            "status": "active",
            "memory_type": "workflow_note",
            "content": "Run operator proof after tests.",
            "source": "operator_approved",
            "confidence": 0.87,
            "created_at": "2026-06-11T00:00:00Z",
            "updated_at": "2026-06-11T00:00:00Z",
            "supersedes": None,
            "tags": ["workflow"],
            "receipt_label": "Memory XV7-MEMORY-0003",
            "pending_approval": False,
        }
    )

    store.save_record(record)
    loaded = store.get_record("XV7-MEMORY-0003")

    assert loaded is not None
    assert loaded.content == record.content
    assert store.next_memory_id() == "XV7-MEMORY-0004"
