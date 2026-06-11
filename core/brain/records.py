from __future__ import annotations

import json
import os
from pathlib import Path

from core.brain.schema import BrainLayer, BrainRecord


class BrainRecordLoader:
    """Load and validate canonical brain records from disk."""

    def __init__(self, records_dir: Path | None = None) -> None:
        env_path = os.getenv("XV7_BRAIN_RECORDS_PATH")
        if records_dir is not None:
            self.records_dir = records_dir
        elif env_path:
            self.records_dir = Path(env_path)
        else:
            self.records_dir = Path("data/brain/records")

    def load_records(self) -> list[BrainRecord]:
        if not self.records_dir.exists():
            return []

        records: list[BrainRecord] = []
        for path in sorted(self.records_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(BrainRecord.model_validate(payload))

        return records

    def load_active_records(
        self, *, layer: BrainLayer | None = None
    ) -> list[BrainRecord]:
        records = [r for r in self.load_records() if r.status == "active"]
        if layer is not None:
            records = [r for r in records if r.layer == layer]
        return sorted(records, key=lambda r: (r.layer.value, -r.priority, r.record_id))
