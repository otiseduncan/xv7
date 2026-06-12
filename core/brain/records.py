from __future__ import annotations

import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone

from core.brain.schema import BrainLayer, BrainRecord


class BrainRecordLoader:
    """Load and validate canonical brain records from disk."""

    def __init__(
        self,
        records_dir: Path | None = None,
        runtime_records_dir: Path | None = None,
    ) -> None:
        env_path = os.getenv("XV7_BRAIN_RECORDS_PATH")
        runtime_env_path = os.getenv("XV7_BRAIN_RUNTIME_RECORDS_PATH")
        runtime_fallback_env_path = os.getenv("XV7_BRAIN_RUNTIME_FALLBACK_PATH")
        allow_seed_writes = os.getenv("XV7_ALLOW_BRAIN_SEED_WRITES") == "1"
        if records_dir is not None:
            self.records_dir = records_dir
        elif env_path:
            self.records_dir = Path(env_path)
        else:
            self.records_dir = Path("data/brain/records")

        if runtime_records_dir is not None:
            self.runtime_records_dir = runtime_records_dir
        elif runtime_env_path:
            runtime_path = Path(runtime_env_path)
            if self._same_path(runtime_path, self.records_dir) and not allow_seed_writes:
                if runtime_fallback_env_path:
                    self.runtime_records_dir = Path(runtime_fallback_env_path)
                else:
                    self.runtime_records_dir = Path("data/brain/runtime_records")
            else:
                self.runtime_records_dir = runtime_path
        elif records_dir is not None:
            self.runtime_records_dir = self.records_dir
        else:
            self.runtime_records_dir = Path("data/brain/runtime_records")

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        try:
            return left.resolve(strict=False) == right.resolve(strict=False)
        except OSError:
            return left.absolute() == right.absolute()

    def _prepare_runtime_record_store(self) -> None:
        try:
            self.runtime_records_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"runtime record store is unavailable: {self.runtime_records_dir}"
            ) from exc

        if not self.runtime_records_dir.is_dir():
            raise RuntimeError(
                f"runtime record store is not a directory: {self.runtime_records_dir}"
            )

        probe_path = self.runtime_records_dir / ".xv7-write-test"
        try:
            probe_path.write_text("xv7\n", encoding="utf-8")
            probe_path.unlink()
        except OSError as exc:
            raise RuntimeError(
                f"runtime record store is not writable: {self.runtime_records_dir}"
            ) from exc

    @staticmethod
    def _load_dir_records(records_dir: Path) -> dict[str, BrainRecord]:
        if not records_dir.exists():
            return {}

        records: dict[str, BrainRecord] = {}
        for path in sorted(records_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = BrainRecord.model_validate(payload)
            records[record.record_id] = record
        return records

    def load_records(self) -> list[BrainRecord]:
        merged_records = self._load_dir_records(self.records_dir)
        if not self._same_path(self.runtime_records_dir, self.records_dir):
            merged_records.update(self._load_dir_records(self.runtime_records_dir))
        return [merged_records[record_id] for record_id in sorted(merged_records)]

    def load_records_with_source(self) -> list[tuple[BrainRecord, str, Path]]:
        seed_records = self._load_dir_records(self.records_dir)
        runtime_records: dict[str, BrainRecord] = {}
        if not self._same_path(self.runtime_records_dir, self.records_dir):
            runtime_records = self._load_dir_records(self.runtime_records_dir)

        merged: dict[str, tuple[BrainRecord, str, Path]] = {}
        for record_id, record in seed_records.items():
            merged[record_id] = (
                record,
                "seed",
                self.records_dir / f"{record_id}.json",
            )

        for record_id, record in runtime_records.items():
            merged[record_id] = (
                record,
                "runtime_override",
                self.runtime_records_dir / f"{record_id}.json",
            )

        return [merged[record_id] for record_id in sorted(merged)]

    def get_record_with_source(
        self, record_id: str
    ) -> tuple[BrainRecord, str, Path] | None:
        runtime_path = self.runtime_records_dir / f"{record_id}.json"
        seed_path = self.records_dir / f"{record_id}.json"

        if runtime_path.exists() and not self._same_path(
            self.runtime_records_dir, self.records_dir
        ):
            payload = json.loads(runtime_path.read_text(encoding="utf-8"))
            return BrainRecord.model_validate(payload), "runtime_override", runtime_path

        if seed_path.exists():
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
            return BrainRecord.model_validate(payload), "seed", seed_path

        return None

    @staticmethod
    def record_updated_at(path: Path) -> str:
        ts = path.stat().st_mtime
        return (
            datetime.fromtimestamp(ts, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _selection_priority(record: BrainRecord) -> int:
        """Keep learned-rule overlays from overshadowing canonical layer records."""
        tags = {str(tag).lower() for tag in record.tags}
        if record.layer in {BrainLayer.MEMORY, BrainLayer.KNOWLEDGE} and (
            "learned-rule" in tags or "otis-learning" in tags
        ):
            return record.priority - 1000
        return record.priority

    def load_active_records(
        self, *, layer: BrainLayer | None = None
    ) -> list[BrainRecord]:
        records = [r for r in self.load_records() if r.status == "active"]
        if layer is not None:
            records = [r for r in records if r.layer == layer]
        return sorted(
            records,
            key=lambda r: (r.layer.value, -self._selection_priority(r), r.record_id),
        )

    @staticmethod
    def _focus_index(record_id: str) -> int:
        match = re.match(r"^XV7-FOCUS-(\d{4})$", record_id)
        if match is None:
            return 0
        return int(match.group(1))

    @staticmethod
    def _record_index(record_id: str, token: str) -> int:
        match = re.match(rf"^XV7-{token}-(\d{{4}})$", record_id)
        if match is None:
            return 0
        return int(match.group(1))

    @staticmethod
    def _focus_title(summary: str) -> str:
        cleaned = summary.strip().rstrip(".?!")
        if len(cleaned) <= 88:
            return cleaned
        return cleaned[:85].rstrip() + "..."

    def _runtime_record_path(self, record_id: str) -> Path:
        return self.runtime_records_dir / f"{record_id}.json"

    def _save_record(self, record: BrainRecord) -> None:
        self._prepare_runtime_record_store()
        payload = record.model_dump(mode="json")
        path = self._runtime_record_path(record.record_id)
        temp_path = path.with_name(f".{path.name}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temp_path.replace(path)
            saved_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"failed to write runtime record store record: {record.record_id}"
            ) from exc
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        if saved_payload.get("record_id") != record.record_id:
            raise RuntimeError(
                f"runtime record store verification failed for {record.record_id}"
            )

    def save_runtime_override(self, record: BrainRecord) -> BrainRecord:
        self._save_record(record)
        return record

    def create_learned_rule_record(
        self,
        *,
        layer: BrainLayer,
        title: str,
        summary: str,
        body: str,
        tags: list[str],
        source_user_message: str,
        confidence: float,
        memory_type: str | None,
        status: str,
        proof_required: bool,
    ) -> BrainRecord:
        token = {
            BrainLayer.MEMORY: "MEMORY",
            BrainLayer.KNOWLEDGE: "KNOWLEDGE",
            BrainLayer.VERIFIED_STATUS: "VERIFIED",
            BrainLayer.ACTIVE_FOCUS: "FOCUS",
            BrainLayer.SYSTEM_PROMPT: "SYSTEM",
        }[layer]

        records = self.load_records()
        max_index = max(
            [self._record_index(record.record_id, token) for record in records],
            default=0,
        )
        record_id = f"XV7-{token}-{max_index + 1:04d}"

        normalized_tags = []
        for tag in tags:
            cleaned = str(tag).strip().lower().replace(" ", "-")
            if cleaned and cleaned not in normalized_tags:
                normalized_tags.append(cleaned)
        for required in ("learned-rule", "runtime", "otis-learning"):
            if required not in normalized_tags:
                normalized_tags.append(required)
        if proof_required and "proof-required" not in normalized_tags:
            normalized_tags.append("proof-required")

        rule = BrainRecord.model_validate(
            {
                "record_id": record_id,
                "layer": layer.value,
                "title": title,
                "summary": summary,
                "body": body,
                "memory_type": memory_type,
                "status": status,
                "priority": 220 if status == "active" else 180,
                "tags": normalized_tags,
                "facts": [
                    {
                        "statement": summary,
                        "source_type": "direct_user_instruction",
                        "source_detail": source_user_message,
                    }
                ],
                "evidence": [
                    f"User instruction: {source_user_message}",
                    f"confidence={confidence:.2f}",
                ],
            }
        )
        self._save_record(rule)
        return rule

    def archive_record(self, record_id: str) -> BrainRecord:
        found = self.get_record_with_source(record_id)
        if found is None:
            raise ValueError(f"Record not found: {record_id}")

        record, _, _ = found
        archived_tags = list(record.tags)
        if "deactivated" not in archived_tags:
            archived_tags.append("deactivated")

        updated = record.model_copy(
            update={
                "status": "disabled",
                "tags": archived_tags,
                "relevance_state": "historical",
            }
        )
        self._save_record(updated)
        return updated

    def reject_record(self, record_id: str) -> BrainRecord:
        found = self.get_record_with_source(record_id)
        if found is None:
            raise ValueError(f"Record not found: {record_id}")

        record, _, _ = found
        updated_tags = list(record.tags)
        if "rejected" not in updated_tags:
            updated_tags.append("rejected")

        updated = record.model_copy(
            update={
                "status": "archived",
                "tags": updated_tags,
                "relevance_state": "superseded"
                if record.relevance_state == "current"
                else record.relevance_state,
            }
        )
        self._save_record(updated)
        return updated

    def approve_record(self, record_id: str) -> BrainRecord:
        found = self.get_record_with_source(record_id)
        if found is None:
            raise ValueError(f"Record not found: {record_id}")

        record, _, _ = found
        updated_tags = [tag for tag in record.tags if tag != "rejected"]
        if "approved" not in updated_tags:
            updated_tags.append("approved")

        updated = record.model_copy(
            update={
                "status": "active",
                "tags": updated_tags,
                "relevance_state": "current",
            }
        )
        self._save_record(updated)
        return updated

    def set_record_active(self, record_id: str) -> BrainRecord:
        found = self.get_record_with_source(record_id)
        if found is None:
            raise ValueError(f"Record not found: {record_id}")

        target, _, _ = found
        all_records = self.load_records()

        for record in all_records:
            if record.layer != target.layer:
                continue
            if record.record_id == target.record_id:
                continue
            if record.status != "active":
                continue

            archived_tags = list(record.tags)
            if "superseded" not in archived_tags:
                archived_tags.append("superseded")
            archived = record.model_copy(
                update={
                    "status": "disabled",
                    "tags": archived_tags,
                    "relevance_state": "superseded",
                    "superseded_by": target.record_id,
                }
            )
            self._save_record(archived)

        active_tags = [tag for tag in target.tags if tag != "deactivated"]
        updated = target.model_copy(
            update={
                "status": "active",
                "tags": active_tags,
                "relevance_state": "current",
                "superseded_by": None,
            }
        )
        self._save_record(updated)
        return updated

    def apply_active_focus_instruction(self, focus_summary: str) -> BrainRecord:
        cleaned_summary = " ".join(focus_summary.strip().split())
        self._prepare_runtime_record_store()
        records = self.load_records()

        active_focus_records = [
            record
            for record in records
            if record.layer == BrainLayer.ACTIVE_FOCUS and record.status == "active"
        ]
        max_focus_index = max(
            [self._focus_index(record.record_id) for record in records],
            default=0,
        )
        next_record_id = f"XV7-FOCUS-{max_focus_index + 1:04d}"

        for record in active_focus_records:
            archived_tags = list(record.tags)
            if "superseded" not in archived_tags:
                archived_tags.append("superseded")

            archived = record.model_copy(
                update={
                    "status": "archived",
                    "tags": archived_tags,
                    "relevance_state": "superseded",
                    "superseded_by": next_record_id,
                }
            )
            self._save_record(archived)

        new_record = BrainRecord.model_validate(
            {
                "record_id": next_record_id,
                "layer": "active_focus",
                "title": self._focus_title(cleaned_summary),
                "summary": cleaned_summary,
                "body": (
                    "Direct user instruction sets current working Active Focus: "
                    f"{cleaned_summary}"
                ),
                "status": "active",
                "priority": 300,
                "tags": ["focus", "user-instruction", "working-context"],
                "facts": [
                    {
                        "statement": f"Current user-directed active focus: {cleaned_summary}",
                        "source_type": "direct_user_instruction",
                        "source_detail": "otis verbal focus instruction",
                    }
                ],
                "evidence": [
                    f"Direct user instruction: {cleaned_summary}",
                ],
            }
        )
        self._save_record(new_record)
        return new_record
