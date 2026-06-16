from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re

from core.memory.schema import MemoryRecord, MemorySource, MemoryType
from core.memory.store import MemoryStore


@dataclass
class MemoryActionResult:
    answer: str
    receipt: str
    metadata_updates: dict[str, object] = field(default_factory=dict)


class PersistentMemoryManager:
    """Policy and lifecycle manager for XV7 persistent memory."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _find_active_memory_by_content(
        self,
        *,
        content: str,
        memory_type: MemoryType,
    ) -> MemoryRecord | None:
        normalized_content = self._normalize(content)
        for record in self.list_active_memories():
            if record.memory_type != memory_type:
                continue
            if self._normalize(record.content) == normalized_content:
                return record
        return None

    @staticmethod
    def _metadata_string_list(metadata: dict[str, object], key: str) -> list[str]:
        raw = metadata.get(key)
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, str)]

    @staticmethod
    def _simple_tags(text: str) -> list[str]:
        tags = []
        lower = text.lower()
        if "otis" in lower:
            tags.append("otis")
        if "xv7" in lower:
            tags.append("xv7")
        if "receipt" in lower:
            tags.append("receipt")
        if "proof" in lower:
            tags.append("proof")
        if "verified" in lower:
            tags.append("verified")
        if "memory" in lower:
            tags.append("memory")
        return sorted(set(tags))

    @staticmethod
    def _infer_memory_type(content: str) -> MemoryType:
        lower = content.lower()
        if "prefer" in lower or "wants" in lower:
            if "project" in lower or "xv7" in lower:
                return "project_preference"
            return "user_preference"
        if "remind" in lower:
            return "reminder_candidate"
        if "fix" in lower or "correct" in lower:
            return "correction"
        if "workflow" in lower or "step" in lower:
            return "workflow_note"
        return "project_fact"

    def bootstrap_seed_records(self) -> None:
        existing_ids = {record.id for record in self.store.list_records()}
        now = self._now()
        seeds = [
            MemoryRecord(
                id="XV7-MEMORY-0001",
                status="active",
                memory_type="project_preference",
                content="Otis wants fresh XV7 knowledge, not copied XV6.1 knowledge.",
                source="user_explicit",
                confidence=0.98,
                created_at=now,
                updated_at=now,
                tags=["otis", "xv7", "knowledge", "fresh"],
                receipt_label="Memory XV7-MEMORY-0001",
            ),
            MemoryRecord(
                id="XV7-MEMORY-0002",
                status="active",
                memory_type="workflow_note",
                content="XV6.1 may be used as historical reference only.",
                source="user_explicit",
                confidence=0.96,
                created_at=now,
                updated_at=now,
                tags=["xv6.1", "reference", "workflow"],
                receipt_label="Memory XV7-MEMORY-0002",
            ),
            MemoryRecord(
                id="XV7-MEMORY-0003",
                status="active",
                memory_type="project_preference",
                content="Otis prefers direct, honest, proof-based project updates.",
                source="user_explicit",
                confidence=0.98,
                created_at=now,
                updated_at=now,
                tags=["otis", "proof", "updates"],
                receipt_label="Memory XV7-MEMORY-0003",
            ),
            MemoryRecord(
                id="XV7-MEMORY-0004",
                status="active",
                memory_type="project_preference",
                content="Otis wants no fake repo checks, no fake memory claims, and no hidden reasoning replay.",
                source="user_explicit",
                confidence=0.99,
                created_at=now,
                updated_at=now,
                tags=["otis", "repo", "memory", "reasoning", "safety"],
                receipt_label="Memory XV7-MEMORY-0004",
            ),
        ]
        for seed in seeds:
            if seed.id not in existing_ids:
                self.store.save_record(seed)

    def create_pending_memory(
        self,
        *,
        content: str,
        source: MemorySource = "assistant_observed",
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        now = self._now()
        memory_id = self.store.next_memory_id()
        record = MemoryRecord(
            id=memory_id,
            status="inactive",
            memory_type=memory_type or self._infer_memory_type(content),
            content=content.strip(),
            source=source,
            confidence=0.45,
            created_at=now,
            updated_at=now,
            tags=sorted(set((tags or []) + self._simple_tags(content))),
            receipt_label=f"Memory {memory_id} pending",
            pending_approval=True,
        )
        return self.store.save_record(record)

    def create_active_memory(
        self,
        *,
        content: str,
        source: MemorySource = "user_explicit",
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.95,
    ) -> MemoryRecord:
        now = self._now()
        memory_id = self.store.next_memory_id()
        record = MemoryRecord(
            id=memory_id,
            status="active",
            memory_type=memory_type or self._infer_memory_type(content),
            content=content.strip(),
            source=source,
            confidence=max(0.0, min(1.0, confidence)),
            created_at=now,
            updated_at=now,
            tags=sorted(set((tags or []) + self._simple_tags(content))),
            receipt_label=f"Memory {memory_id}",
            pending_approval=False,
        )
        return self.store.save_record(record)

    def upsert_active_memory(
        self,
        *,
        content: str,
        source: MemorySource = "user_explicit",
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.95,
    ) -> MemoryRecord:
        chosen_type = memory_type or self._infer_memory_type(content)
        existing = self._find_active_memory_by_content(
            content=content,
            memory_type=chosen_type,
        )
        if existing is not None:
            existing.content = content.strip()
            existing.source = source
            existing.confidence = max(existing.confidence, confidence)
            existing.updated_at = self._now()
            existing.tags = sorted(
                set(existing.tags + (tags or []) + self._simple_tags(content))
            )
            existing.pending_approval = False
            if not existing.receipt_label.lower().startswith("memory "):
                existing.receipt_label = f"Memory {existing.id}"
            return self.store.save_record(existing)

        return self.create_active_memory(
            content=content,
            source=source,
            memory_type=chosen_type,
            tags=tags,
            confidence=confidence,
        )

    def approve_memory(self, memory_id: str) -> MemoryRecord:
        record = self.store.get_record(memory_id)
        if record is None:
            raise ValueError(f"Memory not found: {memory_id}")
        record.pending_approval = False
        if record.status == "inactive":
            record.receipt_label = f"Memory {record.id} approved"
        record.updated_at = self._now()
        return self.store.save_record(record)

    def activate_memory(self, memory_id: str) -> MemoryRecord:
        record = self.store.get_record(memory_id)
        if record is None:
            raise ValueError(f"Memory not found: {memory_id}")
        record.status = "active"
        record.pending_approval = False
        record.receipt_label = f"Memory {record.id}"
        record.updated_at = self._now()
        return self.store.save_record(record)

    def supersede_memory(
        self,
        memory_id: str,
        *,
        new_content: str,
        source: MemorySource = "user_explicit",
    ) -> MemoryRecord:
        current = self.store.get_record(memory_id)
        if current is None:
            raise ValueError(f"Memory not found: {memory_id}")
        current.status = "superseded"
        current.updated_at = self._now()
        self.store.save_record(current)

        replacement = self.create_active_memory(
            content=new_content,
            source=source,
            memory_type=current.memory_type,
            tags=current.tags,
            confidence=max(0.5, current.confidence),
        )
        replacement.supersedes = current.id
        replacement.updated_at = self._now()
        return self.store.save_record(replacement)

    def soft_delete_memory(self, memory_id: str) -> MemoryRecord:
        record = self.store.get_record(memory_id)
        if record is None:
            raise ValueError(f"Memory not found: {memory_id}")
        record.status = "deleted"
        record.pending_approval = False
        record.updated_at = self._now()
        record.receipt_label = f"Memory {record.id} deleted"
        return self.store.save_record(record)

    def list_active_memories(self) -> list[MemoryRecord]:
        return [
            record
            for record in self.store.list_records()
            if record.status == "active" and not record.pending_approval
        ]

    def search_memories(
        self,
        *,
        query: str = "",
        tags: list[str] | None = None,
        include_pending: bool = False,
    ) -> list[MemoryRecord]:
        tag_set = {tag.lower() for tag in (tags or []) if tag.strip()}
        needle = query.lower().strip()
        tokens = [
            token for token in re.findall(r"[a-z0-9_.-]+", needle) if len(token) > 1
        ]
        matches: list[MemoryRecord] = []
        for record in self.store.list_records():
            is_active = record.status == "active" and not record.pending_approval
            is_pending = record.pending_approval and record.status == "inactive"
            if not is_active and not (include_pending and is_pending):
                continue

            haystack = f"{record.content} {' '.join(record.tags)}".lower()
            if tag_set and not tag_set.intersection({t.lower() for t in record.tags}):
                continue
            if needle and tokens and not all(token in haystack for token in tokens):
                continue
            if needle and not tokens and needle not in haystack:
                continue
            matches.append(record)
        return sorted(matches, key=lambda r: r.id)

    @staticmethod
    def compact_receipt(records: list[MemoryRecord], *, pending_count: int = 0) -> str:
        if not records:
            suffix = f" pending={pending_count}" if pending_count else ""
            return f"Context receipt: Memory none (active=0{suffix})."
        joined = ", ".join(f"{record.id}" for record in records)
        suffix = f"; pending={pending_count}" if pending_count else ""
        return f"Context receipt: Memory {joined} (active={len(records)}{suffix})."

    def _subject_query(self, normalized: str) -> str:
        match = re.match(r"what do you remember about (.+?)(\?)?$", normalized)
        if not match:
            return ""
        return match.group(1).strip()

    def _status_line(self, record: MemoryRecord) -> str:
        pending = "pending" if record.pending_approval else "not-pending"
        return (
            f"{record.id}: status={record.status}, {pending}, "
            f"source={record.source}, confidence={record.confidence:.2f}"
        )

    def _active_by_query(self, query: str) -> list[MemoryRecord]:
        return self.search_memories(query=query)

    def _pending_by_query(self, query: str) -> list[MemoryRecord]:
        pending = self.search_memories(query=query, include_pending=True)
        return [record for record in pending if record.pending_approval]

    def _recall_answer(self, query: str) -> MemoryActionResult:
        active = self.search_memories(query=query)
        pending = self.search_memories(query=query, include_pending=True)
        pending_only = [r for r in pending if r.pending_approval]

        if not active:
            answer = "I do not have relevant active memory records for that yet."
            if pending_only:
                pending_ids = ", ".join(record.id for record in pending_only)
                answer += (
                    f" I do have pending memory candidate(s): {pending_ids}, "
                    "which are not active until approved."
                )
            return MemoryActionResult(
                answer=answer,
                receipt=self.compact_receipt([], pending_count=len(pending_only)),
                metadata_updates={"last_memory_match_ids": []},
            )

        lines = ["Remembered items (Memory records only):"]
        for record in active:
            lines.append(f"- {record.id}: {record.content}")
        if pending_only:
            lines.append(
                "Pending (not active): "
                + ", ".join(record.id for record in pending_only)
            )
        return MemoryActionResult(
            answer="\n".join(lines),
            receipt=self.compact_receipt(active, pending_count=len(pending_only)),
            metadata_updates={
                "last_memory_match_ids": [record.id for record in active]
            },
        )

    def try_handle_chat(
        self,
        question: str,
        *,
        session_metadata: dict[str, object] | None = None,
    ) -> MemoryActionResult | None:
        metadata = session_metadata or {}

        normalized = self._normalize(question)
        normalized_core = normalized.strip(" .!?")

        if normalized_core in {
            "forget everything",
            "delete all memories",
            "replace all memory with this one",
        }:
            return MemoryActionResult(
                answer=(
                    "I will not mass-delete or replace all memory without an explicit safe workflow. "
                    "Please target a specific memory record."
                ),
                receipt=self.compact_receipt(self.list_active_memories()),
            )

        if normalized_core in {"import all xv6.1 memory", "import all xv6.1 memories"}:
            return MemoryActionResult(
                answer=(
                    "I cannot bulk import XV6.1 memory for B6. "
                    "Only fresh XV7-native memory is allowed; XV6.1 is historical reference only."
                ),
                receipt=self.compact_receipt(self.list_active_memories()),
            )

        if normalized_core in {
            "treat this guess as verified memory",
            "treat this guess as verified",
        }:
            return MemoryActionResult(
                answer=(
                    "I will not store guesses as verified memory. "
                    "I can store a guess only as unverified memory candidate if explicitly requested."
                ),
                receipt=self.compact_receipt(self.list_active_memories()),
            )

        if normalized_core in {
            "i like that.",
            "i like that",
            "that was important.",
            "that was important",
            "remember that.",
            "remember that",
            "save this preference.",
            "save this preference",
            "make a note of it.",
            "make a note of it",
        }:
            return MemoryActionResult(
                answer=(
                    "I did not store memory because the target is ambiguous. "
                    "Please provide explicit text, for example: 'Remember this: <content>'."
                ),
                receipt=self.compact_receipt(self.list_active_memories()),
            )

        if (
            normalized_core.startswith("remember this:")
            or normalized_core.startswith("remember this ")
            or normalized_core.startswith("remember this for xv7:")
        ):
            content = question.split(":", 1)[1].strip() if ":" in question else ""
            if not content:
                return MemoryActionResult(
                    answer="I can store that, but I need the exact memory text after 'Remember this:'.",
                    receipt=self.compact_receipt([]),
                )
            created = self.create_active_memory(content=content, source="user_explicit")
            return MemoryActionResult(
                answer=f"Stored as active memory {created.id}: {created.content}",
                receipt=self.compact_receipt([created]),
                metadata_updates={"last_memory_match_ids": [created.id]},
            )

        if normalized_core in {
            "do you have any pending memories?",
            "do you have any pending memories",
            "what pending memory is waiting for approval?",
            "what pending memory is waiting for approval",
        }:
            pending = self._pending_by_query("")
            if not pending:
                return MemoryActionResult(
                    answer="No pending memory candidates are waiting for approval.",
                    receipt=self.compact_receipt([], pending_count=0),
                )
            lines = ["Pending memories (not active):"]
            lines.extend(f"- {self._status_line(record)}" for record in pending)
            return MemoryActionResult(
                answer="\n".join(lines),
                receipt=self.compact_receipt([], pending_count=len(pending)),
                metadata_updates={
                    "last_memory_match_ids": [record.id for record in pending]
                },
            )

        if normalized_core in {
            "what active memories do you have now?",
            "what active memories do you have now",
        }:
            active = self.list_active_memories()
            if not active:
                return MemoryActionResult(
                    answer="I do not have active memories right now.",
                    receipt=self.compact_receipt([]),
                )
            lines = ["Active memories:"]
            lines.extend(f"- {self._status_line(record)}" for record in active)
            return MemoryActionResult(
                answer="\n".join(lines),
                receipt=self.compact_receipt(active),
                metadata_updates={
                    "last_memory_match_ids": [record.id for record in active]
                },
            )

        if normalized_core.startswith("approve the pending "):
            query = normalized_core.replace("approve the pending", "", 1).strip(" .")
            pending = self._pending_by_query(query)
            if not pending:
                return MemoryActionResult(
                    answer="I did not find a matching pending memory to approve.",
                    receipt=self.compact_receipt([], pending_count=0),
                )
            if len(pending) > 1:
                return MemoryActionResult(
                    answer=(
                        "Approval target is ambiguous. Please specify one ID: "
                        + ", ".join(record.id for record in pending)
                    ),
                    receipt=self.compact_receipt([], pending_count=len(pending)),
                )
            approved = self.approve_memory(pending[0].id)
            activated = self.activate_memory(approved.id)
            return MemoryActionResult(
                answer=f"Approved and activated memory {activated.id}: {activated.content}",
                receipt=self.compact_receipt([activated]),
                metadata_updates={"last_memory_match_ids": [activated.id]},
            )

        if normalized_core in {
            "is that memory active yet",
            "is that memory active yet?",
        }:
            candidate_ids = self._metadata_string_list(
                metadata, "last_memory_match_ids"
            )
            if not candidate_ids:
                return MemoryActionResult(
                    answer="I do not have a specific memory target to check.",
                    receipt=self.compact_receipt([]),
                )
            record = self.store.get_record(candidate_ids[0])
            if record is None:
                return MemoryActionResult(
                    answer="That memory record is no longer available.",
                    receipt=self.compact_receipt([]),
                )
            return MemoryActionResult(
                answer=f"{record.id} is currently {record.status} (pending_approval={record.pending_approval}).",
                receipt=self.compact_receipt(
                    [record]
                    if record.status == "active" and not record.pending_approval
                    else [],
                    pending_count=1 if record.pending_approval else 0,
                ),
            )

        if normalized_core in {"what do you remember", "what do you remember?"}:
            return self._recall_answer("")

        if normalized_core in {
            "what do you remember about me?",
            "what do you remember about me",
        }:
            return self._recall_answer("otis")

        if normalized_core in {
            "what do you remember about my preferences?",
            "what do you remember about my preferences",
        }:
            matches = [
                record
                for record in self.list_active_memories()
                if (
                    record.memory_type in {"user_preference", "project_preference"}
                    or "prefer" in record.content.lower()
                    or "wants" in record.content.lower()
                )
            ]
            if not matches:
                return MemoryActionResult(
                    answer="I do not have relevant active memory records for that yet.",
                    receipt=self.compact_receipt([]),
                    metadata_updates={"last_memory_match_ids": []},
                )
            lines = ["Remembered preference items (Memory records only):"]
            lines.extend(f"- {record.id}: {record.content}" for record in matches)
            return MemoryActionResult(
                answer="\n".join(lines),
                receipt=self.compact_receipt(matches),
                metadata_updates={
                    "last_memory_match_ids": [record.id for record in matches]
                },
            )

        if normalized_core.startswith("what do you remember about "):
            return self._recall_answer(self._subject_query(normalized_core))

        if (
            normalized_core.startswith("is the ")
            and " memory still active" in normalized_core
        ):
            subject = (
                normalized_core.replace("is the", "", 1)
                .replace("memory still active", "")
                .strip(" .?")
            )
            candidates = self.search_memories(query=subject)
            if not candidates:
                return MemoryActionResult(
                    answer=f"I do not have an active memory match for: {subject or 'that subject'}.",
                    receipt=self.compact_receipt([]),
                )
            if len(candidates) > 1:
                return MemoryActionResult(
                    answer=(
                        "That active-status check is ambiguous. Please specify one memory ID: "
                        + ", ".join(record.id for record in candidates)
                    ),
                    receipt=self.compact_receipt(candidates),
                )
            record = candidates[0]
            return MemoryActionResult(
                answer=f"Memory {record.id} is active.",
                receipt=self.compact_receipt([record]),
                metadata_updates={"last_memory_match_ids": [record.id]},
            )

        if normalized_core.startswith("search memory for"):
            query = (
                question.split("for", 1)[1].strip().strip('."')
                if "for" in question.lower()
                else ""
            )
            matches = self.search_memories(query=query)
            if not matches:
                return MemoryActionResult(
                    answer=f"No active memory matched search query: {query or 'empty query'}.",
                    receipt=self.compact_receipt([]),
                )
            lines = [f"Memory search matches for '{query}':"]
            lines.extend(f"- {record.id}: {record.content}" for record in matches)
            return MemoryActionResult(
                answer="\n".join(lines),
                receipt=self.compact_receipt(matches),
                metadata_updates={
                    "last_memory_match_ids": [record.id for record in matches]
                },
            )

        if normalized_core in {
            "what memory records shaped that answer?",
            "what memory records shaped that answer",
            "what context receipt did you use?",
            "what context receipt did you use",
        }:
            candidate_ids = self._metadata_string_list(
                metadata, "last_memory_match_ids"
            )
            if not candidate_ids:
                return MemoryActionResult(
                    answer="No recent memory-record selection is available in this session metadata.",
                    receipt=self.compact_receipt([]),
                )
            records = [self.store.get_record(mid) for mid in candidate_ids]
            active = [
                record
                for record in records
                if record is not None and record.status == "active"
            ]
            if not active:
                return MemoryActionResult(
                    answer="No active memory records are currently shaping this answer.",
                    receipt=self.compact_receipt([]),
                )
            return MemoryActionResult(
                answer="Memory records shaping answer: "
                + ", ".join(record.id for record in active),
                receipt=self.compact_receipt(active),
            )

        if (
            normalized_core.startswith("forget that")
            or normalized_core.startswith("forget the ")
            or normalized_core.startswith("forget my preference")
        ):
            target_text = normalized_core
            target_text = target_text.replace("forget that", "", 1)
            target_text = target_text.replace("forget the", "", 1)
            target_text = target_text.replace("forget my preference", "", 1)
            target_text = target_text.strip(" .")
            target_text = re.sub(
                r"\b(memory|preference|about|my|the|that)\b", " ", target_text
            )
            target_text = " ".join(target_text.split())
            if target_text:
                candidates = self.search_memories(query=target_text)
                if len(candidates) <= 1 and "receipt" in target_text:
                    candidates = self.search_memories(query="receipt")
                candidate_ids = [record.id for record in candidates]
            else:
                candidate_ids = self._metadata_string_list(
                    metadata, "last_memory_match_ids"
                )

            if not candidate_ids:
                candidate_ids = self._metadata_string_list(
                    metadata, "last_memory_match_ids"
                )

            if not candidate_ids:
                return MemoryActionResult(
                    answer=(
                        "I do not have a clear memory target to forget. "
                        "Please specify what to forget, for example: 'Forget memory XV7-MEMORY-0005'."
                    ),
                    receipt=self.compact_receipt([]),
                )
            if len(candidate_ids) > 1:
                return MemoryActionResult(
                    answer=(
                        "That matches multiple memories, so I will not delete yet. "
                        "Please specify one memory ID: " + ", ".join(candidate_ids)
                    ),
                    receipt=self.compact_receipt([]),
                    metadata_updates={"last_memory_match_ids": candidate_ids},
                )

            deleted = self.soft_delete_memory(candidate_ids[0])
            return MemoryActionResult(
                answer=f"Forgot memory {deleted.id} (soft-deleted; record retained).",
                receipt=self.compact_receipt([]),
                metadata_updates={"last_memory_match_ids": []},
            )

        if normalized_core.startswith(
            "update that memory"
        ) or normalized_core.startswith("update the "):
            new_text = question.split(":", 1)[1].strip() if ":" in question else ""
            if not new_text:
                return MemoryActionResult(
                    answer=(
                        "I can update a memory, but I need the new text. "
                        "Use: 'Update that memory: <new content>'."
                    ),
                    receipt=self.compact_receipt([]),
                )

            query_target = ""
            if normalized_core.startswith("update the "):
                query_target = (
                    normalized_core.replace("update the", "", 1)
                    .split(":", 1)[0]
                    .strip()
                )
                query_target = re.sub(
                    r"\b(memory|preference|about|my|the|that)\b", " ", query_target
                )
                query_target = " ".join(query_target.split())

            if query_target:
                candidate_ids = [
                    record.id for record in self.search_memories(query=query_target)
                ]
            else:
                candidate_ids = self._metadata_string_list(
                    metadata, "last_memory_match_ids"
                )

            if not candidate_ids:
                return MemoryActionResult(
                    answer=(
                        "I do not have a clear memory target to update. "
                        "Please recall it first or provide a memory ID."
                    ),
                    receipt=self.compact_receipt([]),
                )
            if len(candidate_ids) > 1:
                return MemoryActionResult(
                    answer=(
                        "That update target is ambiguous. Please specify one memory ID from: "
                        + ", ".join(candidate_ids)
                    ),
                    receipt=self.compact_receipt([]),
                )

            replacement = self.supersede_memory(candidate_ids[0], new_content=new_text)
            return MemoryActionResult(
                answer=(
                    f"Updated memory by superseding {replacement.supersedes} with {replacement.id}: "
                    f"{replacement.content}"
                ),
                receipt=self.compact_receipt([replacement]),
                metadata_updates={"last_memory_match_ids": [replacement.id]},
            )

        if normalized_core in {
            "did you delete the old receipt memory or supersede it?",
            "did you delete the old receipt memory or supersede it",
        }:
            receipt_related = [
                record
                for record in self.store.list_records()
                if "receipt" in record.content.lower()
                or "receipt" in " ".join(record.tags).lower()
            ]
            superseded_ids = [
                record.id for record in receipt_related if record.status == "superseded"
            ]
            deleted_ids = [
                record.id for record in receipt_related if record.status == "deleted"
            ]
            active_ids = [
                record.id for record in receipt_related if record.status == "active"
            ]
            answer = (
                f"Receipt-memory lifecycle: active={active_ids or ['none']}, "
                f"superseded={superseded_ids or ['none']}, deleted={deleted_ids or ['none']}."
            )
            return MemoryActionResult(
                answer=answer,
                receipt=self.compact_receipt(
                    [record for record in receipt_related if record.status == "active"]
                ),
            )

        if normalized_core in {
            "show the receipt memory status",
            "show the receipt memory status.",
        }:
            matches = self.search_memories(query="receipt", include_pending=True)
            if not matches:
                all_receipt = [
                    record
                    for record in self.store.list_records()
                    if "receipt" in record.content.lower()
                ]
                if not all_receipt:
                    return MemoryActionResult(
                        answer="No receipt-related memory records found.",
                        receipt=self.compact_receipt([]),
                    )
                lines = ["Receipt memory statuses:"]
                lines.extend(f"- {self._status_line(record)}" for record in all_receipt)
                return MemoryActionResult(
                    answer="\n".join(lines),
                    receipt=self.compact_receipt(
                        [record for record in all_receipt if record.status == "active"]
                    ),
                )

            lines = ["Receipt memory statuses:"]
            lines.extend(f"- {self._status_line(record)}" for record in matches)
            return MemoryActionResult(
                answer="\n".join(lines),
                receipt=self.compact_receipt(
                    [record for record in matches if record.status == "active"],
                    pending_count=len(
                        [record for record in matches if record.pending_approval]
                    ),
                ),
                metadata_updates={
                    "last_memory_match_ids": [record.id for record in matches]
                },
            )

        if normalized_core in {
            "is that memory verified or just remembered?",
            "is that memory verified or remembered?",
            "is that verified or just remembered?",
            "is that verified or remembered?",
            "is that memory verified or just remembered",
            "is that memory verified or remembered",
            "is that verified or just remembered",
            "is that verified or remembered",
        }:
            candidate_ids = self._metadata_string_list(
                metadata, "last_memory_match_ids"
            )
            if not candidate_ids:
                return MemoryActionResult(
                    answer=(
                        "I can only classify a specific memory after one is referenced. "
                        "Memory records are remembered context, not verified-status proof."
                    ),
                    receipt=self.compact_receipt([]),
                )

            record = self.store.get_record(candidate_ids[0])
            if record is None:
                return MemoryActionResult(
                    answer="That memory record is no longer available.",
                    receipt=self.compact_receipt([]),
                )

            if record.pending_approval or record.status == "inactive":
                return MemoryActionResult(
                    answer=(
                        f"Memory {record.id} is pending/inactive memory, not verified status. "
                        "It must be approved and activated before active recall."
                    ),
                    receipt=self.compact_receipt([], pending_count=1),
                )

            return MemoryActionResult(
                answer=(
                    f"Memory {record.id} is remembered context, not verified status. "
                    f"Source={record.source}, confidence={record.confidence:.2f}."
                ),
                receipt=self.compact_receipt([record]),
            )

        return None
