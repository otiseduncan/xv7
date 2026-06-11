from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import os

from core.memory.maintenance import MemoryMaintenanceService
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore


def _service(tmp_path: Path) -> MemoryMaintenanceService:
    store = MemoryStore(records_dir=tmp_path / "records")
    manager = PersistentMemoryManager(store=store)
    manager.bootstrap_seed_records()
    return MemoryMaintenanceService(store=store)


def test_duplicate_detector_finds_same_content_active_memories(tmp_path: Path) -> None:
    service = _service(tmp_path)
    manager = service.manager
    manager.create_active_memory(content="Otis wants receipts to stay compact.")
    manager.create_active_memory(content="Otis wants receipts to stay compact")

    duplicates = service.find_duplicate_candidates()
    assert duplicates
    assert any("receipt" in ",".join(item.shared_tags) for item in duplicates)


def test_duplicate_detector_ignores_deleted_records(tmp_path: Path) -> None:
    service = _service(tmp_path)
    manager = service.manager
    first = manager.create_active_memory(content="Otis wants receipts to stay compact.")
    second = manager.create_active_memory(content="Otis wants receipts to stay compact")
    service.soft_delete_by_id(second.id)

    duplicates = service.find_duplicate_candidates()
    ids = {(item.primary_id, item.duplicate_id) for item in duplicates}
    assert (first.id, second.id) not in ids


def test_soft_delete_preserves_file_and_changes_status(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.manager.create_active_memory(
        content="temporary memory for delete test"
    )
    path = service.store.records_dir / f"{created.id}.json"
    assert path.exists()

    deleted = service.soft_delete_by_id(created.id)
    assert deleted.status == "deleted"
    assert path.exists()


def test_restore_reactivates_soft_deleted_memory(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.manager.create_active_memory(
        content="temporary memory for restore test"
    )
    service.soft_delete_by_id(created.id)

    restored = service.restore_by_id(created.id)
    assert restored.status == "active"


def test_audit_summary_counts_statuses(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.manager.create_pending_memory(content="pending candidate")
    service.soft_delete_by_id("XV7-MEMORY-0002")
    service.manager.supersede_memory("XV7-MEMORY-0003", new_content="updated")

    summary = service.audit_summary()
    assert summary["total_records"] >= 5
    assert summary["status_counts"]["deleted"] >= 1
    assert summary["status_counts"]["superseded"] >= 1
    assert summary["pending_count"] >= 1
    assert created.id in [record.id for record in service.list_all()]


def test_destructive_range_requires_exact_confirmation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    records_dir = str(service.store.records_dir)
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)

    missing_confirm = subprocess.run(
        [
            sys.executable,
            "scripts/memory_maintenance.py",
            "soft-delete-range",
            "--records-dir",
            records_dir,
            "--from",
            "XV7-MEMORY-0001",
            "--to",
            "XV7-MEMORY-0002",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo_root),
        env=env,
    )
    assert missing_confirm.returncode == 2
    assert "requires --confirm" in (missing_confirm.stdout + missing_confirm.stderr)

    with_confirm = subprocess.run(
        [
            sys.executable,
            "scripts/memory_maintenance.py",
            "soft-delete-range",
            "--records-dir",
            records_dir,
            "--from",
            "XV7-MEMORY-0001",
            "--to",
            "XV7-MEMORY-0002",
            "--confirm",
            "SOFT DELETE TEST MEMORIES",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo_root),
        env=env,
    )
    assert with_confirm.returncode == 0
    assert "Soft-deleted ids" in with_confirm.stdout
