from __future__ import annotations

from pathlib import Path

from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore


def _snapshot_real_ids() -> list[str]:
    records_dir = Path("data/memory/records")
    if not records_dir.exists():
        return []
    return sorted(path.name for path in records_dir.glob("XV7-MEMORY-*.json"))


def test_memory_store_uses_temporary_directory(tmp_path: Path) -> None:
    store = MemoryStore(records_dir=tmp_path / "isolated_records")
    manager = PersistentMemoryManager(store=store)
    manager.bootstrap_seed_records()
    manager.create_active_memory(content="temp-only memory")

    files = sorted(path.name for path in store.records_dir.glob("XV7-MEMORY-*.json"))
    assert files
    assert store.records_dir != Path("data/memory/records")


def test_memory_test_operations_do_not_mutate_real_records(tmp_path: Path) -> None:
    before = _snapshot_real_ids()

    store = MemoryStore(records_dir=tmp_path / "isolated_records")
    manager = PersistentMemoryManager(store=store)
    manager.bootstrap_seed_records()
    created = manager.create_active_memory(content="temp isolation test memory")
    manager.soft_delete_memory(created.id)

    after = _snapshot_real_ids()
    assert before == after
