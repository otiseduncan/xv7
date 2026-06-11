from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from core.memory.manager import PersistentMemoryManager
from core.memory.schema import MemoryRecord
from core.memory.store import MemoryStore


SEED_MEMORY_IDS = {
    "XV7-MEMORY-0001",
    "XV7-MEMORY-0002",
    "XV7-MEMORY-0003",
    "XV7-MEMORY-0004",
}


@dataclass
class DuplicateCandidate:
    primary_id: str
    duplicate_id: str
    similarity: float
    shared_tags: list[str]
    memory_type: str
    source: str


class MemoryMaintenanceService:
    """Maintenance operations for persistent memory records."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self.manager = PersistentMemoryManager(store=self.store)

    @staticmethod
    def _normalize_content(text: str) -> str:
        lowered = text.lower().strip()
        cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
        return " ".join(cleaned.split())

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def list_all(self) -> list[MemoryRecord]:
        return self.store.list_records()

    def list_active(self) -> list[MemoryRecord]:
        return [
            record
            for record in self.store.list_records()
            if record.status == "active" and not record.pending_approval
        ]

    def list_deleted(self) -> list[MemoryRecord]:
        return [record for record in self.store.list_records() if record.status == "deleted"]

    def find_duplicate_candidates(self) -> list[DuplicateCandidate]:
        active = self.list_active()
        candidates: list[DuplicateCandidate] = []

        for i, left in enumerate(active):
            for right in active[i + 1 :]:
                if left.memory_type != right.memory_type:
                    continue
                if left.source != right.source:
                    continue

                shared_tags = sorted(
                    {tag.lower() for tag in left.tags}.intersection(
                        {tag.lower() for tag in right.tags}
                    )
                )
                if not shared_tags:
                    continue

                left_norm = self._normalize_content(left.content)
                right_norm = self._normalize_content(right.content)
                similarity = self._similarity(left_norm, right_norm)
                if similarity < 0.93:
                    continue

                primary_id = min(left.id, right.id)
                duplicate_id = max(left.id, right.id)
                candidates.append(
                    DuplicateCandidate(
                        primary_id=primary_id,
                        duplicate_id=duplicate_id,
                        similarity=round(similarity, 4),
                        shared_tags=shared_tags,
                        memory_type=left.memory_type,
                        source=left.source,
                    )
                )

        deduped: dict[tuple[str, str], DuplicateCandidate] = {}
        for candidate in candidates:
            deduped[(candidate.primary_id, candidate.duplicate_id)] = candidate
        return [deduped[key] for key in sorted(deduped)]

    def soft_delete_by_id(self, memory_id: str) -> MemoryRecord:
        record = self.store.get_record(memory_id)
        if record is None:
            raise ValueError(f"Memory not found: {memory_id}")
        return self.manager.soft_delete_memory(memory_id)

    def restore_by_id(self, memory_id: str) -> MemoryRecord:
        record = self.store.get_record(memory_id)
        if record is None:
            raise ValueError(f"Memory not found: {memory_id}")
        record.status = "active"
        record.pending_approval = False
        record.updated_at = self.manager._now()
        if not record.receipt_label.lower().startswith("memory "):
            record.receipt_label = f"Memory {record.id}"
        return self.store.save_record(record)

    def soft_delete_duplicates(
        self,
        *,
        include_seeds: bool = False,
    ) -> list[MemoryRecord]:
        duplicates = self.find_duplicate_candidates()
        target_ids = sorted({candidate.duplicate_id for candidate in duplicates})
        if not include_seeds:
            target_ids = [mid for mid in target_ids if mid not in SEED_MEMORY_IDS]
        deleted: list[MemoryRecord] = []
        for memory_id in target_ids:
            deleted.append(self.soft_delete_by_id(memory_id))
        return deleted

    def soft_delete_range(self, start_id: str, end_id: str) -> list[MemoryRecord]:
        all_ids = [record.id for record in self.store.list_records()]
        if start_id not in all_ids:
            raise ValueError(f"Start memory id not found: {start_id}")
        if end_id not in all_ids:
            raise ValueError(f"End memory id not found: {end_id}")
        if start_id > end_id:
            raise ValueError("Range start must be <= range end")

        targets = [mid for mid in all_ids if start_id <= mid <= end_id]
        deleted: list[MemoryRecord] = []
        for memory_id in targets:
            deleted.append(self.soft_delete_by_id(memory_id))
        return deleted

    def audit_summary(self) -> dict[str, Any]:
        records = self.store.list_records()
        status_counts: dict[str, int] = {
            "active": 0,
            "inactive": 0,
            "deleted": 0,
            "superseded": 0,
        }
        pending_count = 0
        for record in records:
            status_counts[record.status] = status_counts.get(record.status, 0) + 1
            if record.pending_approval:
                pending_count += 1

        duplicates = self.find_duplicate_candidates()
        return {
            "records_dir": str(self.store.records_dir),
            "total_records": len(records),
            "status_counts": status_counts,
            "pending_count": pending_count,
            "seed_ids": sorted(SEED_MEMORY_IDS),
            "duplicate_candidates": [asdict(item) for item in duplicates],
        }

    def export_audit(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.audit_summary()
        out_path.write_text(
            __import__("json").dumps(payload, indent=2),
            encoding="utf-8",
        )
        return out_path
