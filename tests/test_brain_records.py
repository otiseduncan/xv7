from __future__ import annotations

from core.brain.records import BrainRecordLoader
from core.brain.schema import BrainLayer


def test_seed_brain_records_load_and_include_required_ids() -> None:
    loader = BrainRecordLoader()
    records = loader.load_active_records()
    ids = {record.record_id for record in records}

    assert "XV7-SYSTEM-0001" in ids
    assert "XV7-FOCUS-0003" in ids
    assert "XV7-KNOWLEDGE-0002" in ids
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
