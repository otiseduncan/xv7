from __future__ import annotations

from pathlib import Path

from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore


def _manager(tmp_path: Path) -> PersistentMemoryManager:
    store = MemoryStore(records_dir=tmp_path / "records")
    manager = PersistentMemoryManager(store=store)
    manager.bootstrap_seed_records()
    return manager


def test_active_listing_excludes_deleted_superseded_and_inactive(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    pending = manager.create_pending_memory(content="Possibly prefers verbose details.")
    manager.soft_delete_memory("XV7-MEMORY-0002")
    manager.supersede_memory("XV7-MEMORY-0003", new_content="Otis prefers concise updates.")

    active_ids = {record.id for record in manager.list_active_memories()}
    assert "XV7-MEMORY-0002" not in active_ids
    assert "XV7-MEMORY-0003" not in active_ids
    assert pending.id not in active_ids


def test_pending_memory_not_active_until_approved_and_activated(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    pending = manager.create_pending_memory(content="Assistant inferred a preference.")

    active_ids = {record.id for record in manager.list_active_memories()}
    assert pending.id not in active_ids

    manager.approve_memory(pending.id)
    manager.activate_memory(pending.id)

    active_ids = {record.id for record in manager.list_active_memories()}
    assert pending.id in active_ids


def test_soft_delete_keeps_record_but_removes_active_recall(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    deleted = manager.soft_delete_memory("XV7-MEMORY-0001")
    assert deleted.status == "deleted"
    assert manager.store.get_record("XV7-MEMORY-0001") is not None
    assert "XV7-MEMORY-0001" not in {r.id for r in manager.list_active_memories()}


def test_supersession_replaces_old_memory_in_active_recall(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    replacement = manager.supersede_memory(
        "XV7-MEMORY-0004",
        new_content="Otis requires transparent, proof-based updates.",
    )
    active_ids = {record.id for record in manager.list_active_memories()}
    assert "XV7-MEMORY-0004" not in active_ids
    assert replacement.id in active_ids
    old = manager.store.get_record("XV7-MEMORY-0004")
    assert old is not None and old.status == "superseded"


def test_memory_search_returns_compact_receipt(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    matches = manager.search_memories(query="proof")
    receipt = manager.compact_receipt(matches)
    assert matches
    assert "Context receipt:" in receipt
    assert "Memory" in receipt


def test_chat_memory_recall_and_verified_separation(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    recall = manager.try_handle_chat("What do you remember about XV7?", session_metadata={})
    assert recall is not None
    assert "Memory records only" in recall.answer

    metadata = {"last_memory_match_ids": recall.metadata_updates.get("last_memory_match_ids", [])}
    separation = manager.try_handle_chat(
        "Is that verified or just remembered?",
        session_metadata=metadata,
    )
    assert separation is not None
    assert "not verified status" in separation.answer


def test_forget_that_requires_unambiguous_match(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.create_active_memory(content="Receipts should stay compact for chat.")
    manager.create_active_memory(content="Receipts should include memory IDs.")

    result = manager.try_handle_chat("Forget that receipt memory.", session_metadata={})
    assert result is not None
    assert "matches multiple memories" in result.answer


def test_ambiguous_statements_do_not_auto_store_active_memory(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    before = {record.id for record in manager.list_active_memories()}

    result = manager.try_handle_chat("I like that.", session_metadata={})
    assert result is not None
    assert "did not store memory" in result.answer

    after = {record.id for record in manager.list_active_memories()}
    assert before == after


def test_pending_memory_listing_and_approval(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    pending = manager.create_pending_memory(content="receipt memory candidate")

    listed = manager.try_handle_chat("Do you have any pending memories?", session_metadata={})
    assert listed is not None
    assert pending.id in listed.answer

    approved = manager.try_handle_chat("Approve the pending receipt memory.", session_metadata={})
    assert approved is not None
    assert "Approved and activated" in approved.answer

    status = manager.try_handle_chat(
        "Is that memory active yet?",
        session_metadata={"last_memory_match_ids": [pending.id]},
    )
    assert status is not None
    assert "active" in status.answer


def test_search_memory_results_and_non_matches(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    found = manager.try_handle_chat('Search memory for "XV6.1".', session_metadata={})
    assert found is not None
    assert "XV6.1" in found.answer

    missing = manager.try_handle_chat('Search memory for "beta".', session_metadata={})
    assert missing is not None
    assert "No active memory matched" in missing.answer


def test_update_memory_supersedes_and_status_visible(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    created = manager.create_active_memory(content="Otis wants receipts to stay compact.")
    metadata = {"last_memory_match_ids": [created.id]}

    updated = manager.try_handle_chat(
        "Update that memory: Otis wants receipts compact but still useful.",
        session_metadata=metadata,
    )
    assert updated is not None
    assert "superseding" in updated.answer

    status = manager.try_handle_chat("Show the receipt memory status.", session_metadata={})
    assert status is not None
    assert "Receipt memory statuses:" in status.answer


def test_forget_specific_memory_soft_deletes_without_hard_delete(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    created = manager.create_active_memory(content="Otis wants receipts to stay compact.")

    forgotten = manager.try_handle_chat(
        "Forget the receipt memory.",
        session_metadata={"last_memory_match_ids": [created.id]},
    )
    assert forgotten is not None
    assert "soft-deleted" in forgotten.answer

    record = manager.store.get_record(created.id)
    assert record is not None
    assert record.status == "deleted"


def test_safety_refuses_mass_destructive_memory_commands(tmp_path: Path) -> None:
    manager = _manager(tmp_path)

    forget_all = manager.try_handle_chat("Forget everything.", session_metadata={})
    assert forget_all is not None
    assert "will not mass-delete" in forget_all.answer

    import_all = manager.try_handle_chat("Import all XV6.1 memory.", session_metadata={})
    assert import_all is not None
    assert "cannot bulk import XV6.1" in import_all.answer
