from __future__ import annotations

import json
from pathlib import Path

from core.brain.records import BrainRecordLoader
from core.brain.schema import BrainLayer


def test_seed_brain_records_load_and_include_required_ids() -> None:
    loader = BrainRecordLoader()
    records = loader.load_active_records()
    ids = {record.record_id for record in records}

    assert "XV7-SYSTEM-0001" in ids
    assert "XV7-FOCUS-0004" in ids
    assert "XV7-KNOWLEDGE-0002" in ids
    assert "XV7-KNOWLEDGE-0003" in ids
    assert "XV7-MEMORY-0002" in ids
    assert "XV7-VERIFIED-0001" in ids


def test_memory_and_knowledge_fact_sources_are_distinguished() -> None:
    loader = BrainRecordLoader()

    memory_record = loader.load_active_records(layer=BrainLayer.MEMORY)[0]
    knowledge_record = loader.load_active_records(layer=BrainLayer.KNOWLEDGE)[0]

    memory_sources = {fact.source_type for fact in memory_record.facts}
    knowledge_sources = {fact.source_type for fact in knowledge_record.facts}

    assert "user_stated" in memory_sources
    assert "inferred" in knowledge_sources


def test_verified_status_uses_provenance_sources_only() -> None:
    loader = BrainRecordLoader()
    verified = loader.load_active_records(layer=BrainLayer.VERIFIED_STATUS)[0]
    sources = {fact.source_type for fact in verified.facts}

    assert "verified_output" in sources
    assert "user_confirmed" in sources
    assert "inferred" not in sources


def test_active_focus_runtime_records_override_seed_store(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed_records"
    runtime_dir = tmp_path / "runtime_records"
    seed_dir.mkdir(parents=True, exist_ok=True)

    source_seed_dir = Path("data/brain/records")
    for path in source_seed_dir.glob("*.json"):
        (seed_dir / path.name).write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    loader = BrainRecordLoader(records_dir=seed_dir, runtime_records_dir=runtime_dir)

    new_record = loader.apply_active_focus_instruction(
        "correct communication with Otis and understanding his workflows"
    )

    seed_focus_payload = json.loads(
        (seed_dir / "XV7-FOCUS-0004.json").read_text(encoding="utf-8")
    )
    assert seed_focus_payload["status"] == "active"

    runtime_archived = json.loads(
        (runtime_dir / "XV7-FOCUS-0004.json").read_text(encoding="utf-8")
    )
    assert runtime_archived["status"] == "archived"

    runtime_new = json.loads(
        (runtime_dir / f"{new_record.record_id}.json").read_text(encoding="utf-8")
    )
    assert runtime_new["status"] == "active"
    assert runtime_new["summary"] == new_record.summary

    active_focus_records = loader.load_active_records(layer=BrainLayer.ACTIVE_FOCUS)
    active_ids = {record.record_id for record in active_focus_records}
    assert new_record.record_id in active_ids
    assert "XV7-FOCUS-0004" not in active_ids
