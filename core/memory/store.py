from __future__ import annotations

import json
import os
from pathlib import Path

from core.memory.schema import MemoryRecord


class MemoryStore:
    """JSON-file persistence for XV7 memory records."""

    def __init__(self, records_dir: Path | None = None) -> None:
        env_path = os.getenv("XV7_PERSISTENT_MEMORY_PATH")
        if records_dir is not None:
            self.records_dir = records_dir
        elif env_path:
            self.records_dir = Path(env_path)
        else:
            self.records_dir = Path("data/memory/records")
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, memory_id: str) -> Path:
        return self.records_dir / f"{memory_id}.json"

    def list_records(self) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        if not self.records_dir.exists():
            return records
        for path in sorted(self.records_dir.glob("XV7-MEMORY-*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(MemoryRecord.model_validate(payload))
        return sorted(records, key=lambda r: r.id)

    def get_record(self, memory_id: str) -> MemoryRecord | None:
        path = self._record_path(memory_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MemoryRecord.model_validate(payload)

    def save_record(self, record: MemoryRecord) -> MemoryRecord:
        path = self._record_path(record.id)
        path.write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return record

    def next_memory_id(self) -> str:
        largest = 0
        for record in self.list_records():
            try:
                largest = max(largest, int(record.id.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                continue
        return f"XV7-MEMORY-{largest + 1:04d}"
