from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any

from core.memory.schema import MemoryRecord, MemoryType


class MemorySignal(StrEnum):
    user_preference = "user_preference"
    answer_style_preference = "answer_style_preference"
    communication_preference = "communication_preference"
    workflow_habit = "workflow_habit"
    user_correction = "user_correction"
    project_fact = "project_fact"
    active_focus_candidate = "active_focus_candidate"
    verified_status_candidate = "verified_status_candidate"
    temporary_context = "temporary_context"
    emotional_feedback_unclear = "emotional_feedback_unclear"
    no_memory = "no_memory"


class MemoryDecisionState(StrEnum):
    save_active = "save_active"
    save_pending_review = "save_pending_review"
    ask_clarification = "ask_clarification"
    ignore = "ignore"
    reject_protected = "reject_protected"


@dataclass(frozen=True)
class MemoryCandidate:
    signal: MemorySignal
    content: str
    memory_type: MemoryType
    confidence: float
    tags: list[str] = field(default_factory=list)
    proof_required: bool = False


@dataclass(frozen=True)
class MemoryDecision:
    state: MemoryDecisionState
    signal: MemorySignal
    candidate: MemoryCandidate | None = None
    saved_record: MemoryRecord | None = None
    retrieved_records: list[MemoryRecord] = field(default_factory=list)
    visible_text: str | None = None
    receipt: str | None = None
    metadata_updates: dict[str, object] = field(default_factory=dict)


class MemoryAutoPilotService:
    """Classify user messages into durable memory decisions and retrieval hints."""

    PROTECTED_PATTERN = re.compile(
        r"\b(bypass safety|disable safety|ignore confirmations|expose secrets|leak secrets|"
        r"pretend ci is green|claim verified without proof|delete memory database|"
        r"delete all memories|drop database|truncate|rm -rf)\b",
        flags=re.IGNORECASE,
    )
    EMOTIONAL_ONLY_PATTERN = re.compile(
        r"\b(wrong|bad|screwed up|that was wrong|not what i meant)\b",
        flags=re.IGNORECASE,
    )
    ANSWER_STYLE_PATTERN = re.compile(
        r"\b(long proof dumps|proof dumps|dump proofs|unless i ask|keep it short|"
        r"be concise|direct answers|no long explanations)\b",
        flags=re.IGNORECASE,
    )
    COMMUNICATION_PATTERN = re.compile(
        r"\b(don't want|do not want|going forward|don't guess|do not guess|"
        r"verify repo status first|verify first|be direct|preview first|write files only)\b",
        flags=re.IGNORECASE,
    )
    WORKFLOW_PATTERN = re.compile(
        r"\b(when i say|remember this workflow correction|we always|how i work|"
        r"how i build|from now on|going forward)\b",
        flags=re.IGNORECASE,
    )
    CORRECTION_PATTERN = re.compile(
        r"\b(correction:|no, that is not what i meant|that's not what i meant|"
        r"you are wrong|you're wrong|incorrect|that is wrong)\b",
        flags=re.IGNORECASE,
    )
    ACTIVE_FOCUS_PATTERN = re.compile(
        r"\b(active focus|focus on|change your focus|set active focus|update your active focus|"
        r"your priority is|we need your focus to be)\b",
        flags=re.IGNORECASE,
    )
    VERIFIED_PATTERN = re.compile(
        r"\b(ci is green|repo status is clean|verified|proof|status is green|passed)\b",
        flags=re.IGNORECASE,
    )
    TEMPORARY_PATTERN = re.compile(
        r"\b(for now|temporary|just for this session|right now|today only|for this chat)\b",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(str(text or "").strip().lower().split())

    def intake(
        self,
        message: str,
        *,
        session_metadata: dict[str, Any] | None = None,
        active_records: list[MemoryRecord] | None = None,
    ) -> MemoryDecision:
        metadata = session_metadata or {}
        normalized = self._normalize(message)
        signal = self._classify_signal(normalized)
        proof_present = self._has_proof_metadata(metadata)

        if signal == MemorySignal.verified_status_candidate and str(
            message or ""
        ).strip().endswith("?"):
            signal = MemorySignal.no_memory

        if signal == MemorySignal.emotional_feedback_unclear:
            return MemoryDecision(
                state=MemoryDecisionState.ask_clarification,
                signal=signal,
                visible_text="I caught the correction, but tell me the exact behavior to save.",
            )

        if signal == MemorySignal.verified_status_candidate and not proof_present:
            return MemoryDecision(
                state=MemoryDecisionState.reject_protected,
                signal=signal,
                visible_text=(
                    "I can’t save that as verified status without proof metadata. "
                    "If you want me to remember it, include the proof or live repo check."
                ),
            )

        candidate = self._build_candidate(message, normalized, signal, proof_present)
        if candidate is not None:
            if candidate.signal in {
                MemorySignal.answer_style_preference,
                MemorySignal.communication_preference,
                MemorySignal.workflow_habit,
                MemorySignal.project_fact,
            }:
                return MemoryDecision(
                    state=MemoryDecisionState.save_active,
                    signal=candidate.signal,
                    candidate=candidate,
                    visible_text="Got it — I’ll keep that preference going forward.",
                )
            if candidate.signal == MemorySignal.verified_status_candidate:
                return MemoryDecision(
                    state=MemoryDecisionState.save_pending_review,
                    signal=candidate.signal,
                    candidate=candidate,
                    visible_text=(
                        "Got it — I’ll keep that as an unverified memory candidate until proof is available."
                    ),
                )

        retrieved_records = self.retrieve_active_memories(
            message,
            session_metadata=metadata,
            active_records=active_records,
            signal=signal,
        )
        metadata_updates: dict[str, object] = {
            "auto_memory_context_prompt": self.build_context_prompt(
                message, retrieved_records, session_metadata=metadata
            ),
            "auto_memory_context_receipt": self._build_receipt_text(retrieved_records),
            "auto_memory_record_ids": [record.id for record in retrieved_records],
            "auto_memory_hints": self._build_hints(message, retrieved_records),
        }
        return MemoryDecision(
            state=MemoryDecisionState.ignore,
            signal=signal,
            retrieved_records=retrieved_records,
            metadata_updates=metadata_updates,
        )

    def retrieve_active_memories(
        self,
        message: str,
        *,
        session_metadata: dict[str, Any] | None = None,
        active_records: list[MemoryRecord] | None = None,
        signal: MemorySignal | None = None,
    ) -> list[MemoryRecord]:
        records = list(active_records or [])
        if not records:
            return []

        text = self._normalize(message)
        if signal is None:
            signal = self._classify_signal(text)

        relevant_types = {
            MemorySignal.answer_style_preference: {
                "answer_style_preference",
                "communication_preference",
                "workflow_habit",
                "user_preference",
                "project_preference",
            },
            MemorySignal.communication_preference: {
                "communication_preference",
                "answer_style_preference",
                "workflow_habit",
                "user_preference",
                "project_preference",
            },
            MemorySignal.workflow_habit: {
                "workflow_habit",
                "workflow_note",
                "communication_preference",
                "user_correction",
                "user_preference",
                "project_preference",
            },
            MemorySignal.user_correction: {
                "user_correction",
                "workflow_habit",
                "communication_preference",
                "project_preference",
            },
            MemorySignal.project_fact: {"project_fact", "project_preference"},
            MemorySignal.active_focus_candidate: {"project_fact", "project_preference"},
            MemorySignal.verified_status_candidate: {"project_fact"},
            MemorySignal.no_memory: {
                "answer_style_preference",
                "communication_preference",
                "workflow_habit",
                "user_correction",
                "project_fact",
                "project_preference",
                "user_preference",
                "verified_status",
            },
        }.get(signal, set())

        selected: list[MemoryRecord] = []
        for record in records:
            if record.memory_type not in relevant_types:
                continue
            haystack = f"{record.content} {' '.join(record.tags)}".lower()
            if signal == MemorySignal.answer_style_preference and not any(
                token in haystack
                for token in ("concise", "direct", "proof", "dump", "short")
            ):
                continue
            if signal == MemorySignal.workflow_habit and not any(
                token in haystack
                for token in (
                    "preview",
                    "website",
                    "generate",
                    "write files only",
                    "when i say",
                )
            ):
                continue
            if signal == MemorySignal.communication_preference and not any(
                token in haystack
                for token in ("guess", "verify", "direct", "preview", "files only")
            ):
                continue
            if signal == MemorySignal.verified_status_candidate:
                if not self._has_proof_metadata(session_metadata or {}):
                    continue
            selected.append(record)

        if not selected and signal == MemorySignal.no_memory:
            selected = [
                record for record in records if record.memory_type in relevant_types
            ]

        priority_types: list[str] = []
        if "verified" in text or "status" in text:
            priority_types = [
                "verified_status",
                "active_focus",
                "project_fact",
                "project_preference",
                "user_preference",
                "answer_style_preference",
                "communication_preference",
                "workflow_habit",
                "user_correction",
            ]
        elif "working on" in text or "active focus" in text:
            priority_types = [
                "active_focus",
                "project_fact",
                "project_preference",
                "verified_status",
                "user_preference",
                "answer_style_preference",
                "communication_preference",
                "workflow_habit",
                "user_correction",
            ]

        if priority_types:
            type_priority = {
                memory_type: index for index, memory_type in enumerate(priority_types)
            }
            selected = sorted(
                selected,
                key=lambda record: (
                    type_priority.get(record.memory_type, len(priority_types)),
                    -record.confidence,
                    record.updated_at,
                    record.id,
                ),
            )
        else:
            selected = sorted(
                selected,
                key=lambda record: (record.updated_at, record.confidence, record.id),
                reverse=True,
            )
        return selected[:3]

    def build_context_prompt(
        self,
        message: str,
        records: list[MemoryRecord],
        *,
        session_metadata: dict[str, Any] | None = None,
    ) -> str:
        if not records:
            return ""

        lines = ["--- AUTO MEMORY CONTEXT ---"]
        focus = self._active_focus_summary(session_metadata or {})
        if focus:
            lines.append(f"Active focus: {focus}")
        for record in records:
            lines.append(f"Memory {record.id}: {record.content}")
        lines.append("---------------------------")
        return "\n".join(lines)

    def build_retrieval_receipt(self, records: list[MemoryRecord]) -> dict[str, Any]:
        if not records:
            return {
                "compact": "Context receipt: Memory none (active=0).",
                "record_ids": [],
                "context_receipts": [],
            }
        return {
            "compact": self._build_receipt_text(records),
            "record_ids": [record.id for record in records],
            "context_receipts": [
                {
                    "layer": "memory",
                    "record_id": record.id,
                    "title": record.receipt_label,
                    "receipt_label": f"Memory {record.id}",
                }
                for record in records
            ],
        }

    def build_brain_record_payload(self, record: MemoryRecord) -> dict[str, Any]:
        memory_type = {
            "answer_style_preference": "answer_style",
            "communication_preference": "preference",
            "workflow_habit": "workflow_rule",
            "user_correction": "working_memory",
            "project_fact": "project_note",
            "active_focus_candidate": "working_memory",
            "verified_status_candidate": "diagnostic_rule",
            "temporary_context": "project_note",
        }.get(record.memory_type, "project_note")
        return {
            "record_id": record.id,
            "layer": "memory",
            "title": record.receipt_label,
            "summary": record.content,
            "body": record.content,
            "memory_type": memory_type,
            "status": "active" if record.status == "active" else "pending",
            "relevance_state": "current",
            "priority": 210 if record.status == "active" else 180,
            "tags": list(record.tags),
            "facts": [
                {
                    "statement": record.content,
                    "source_type": "user_stated",
                    "source_detail": record.source,
                }
            ],
            "evidence": [f"memory_id={record.id}", f"memory_type={record.memory_type}"],
        }

    @staticmethod
    def _build_candidate(
        message: str,
        normalized: str,
        signal: MemorySignal,
        proof_present: bool,
    ) -> MemoryCandidate | None:
        if signal == MemorySignal.no_memory:
            return None

        if signal == MemorySignal.answer_style_preference:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="answer_style_preference",
                confidence=0.96,
                tags=["answer-style", "preference"],
            )

        if signal == MemorySignal.communication_preference:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="communication_preference",
                confidence=0.94,
                tags=["communication", "preference"],
            )

        if signal == MemorySignal.workflow_habit:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="workflow_habit",
                confidence=0.95,
                tags=["workflow", "habit"],
            )

        if signal == MemorySignal.user_correction:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="user_correction",
                confidence=0.92,
                tags=["correction"],
            )

        if signal == MemorySignal.project_fact:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="project_fact",
                confidence=0.90,
                tags=["project", "fact"],
            )

        if signal == MemorySignal.active_focus_candidate:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="active_focus_candidate",
                confidence=0.88,
                tags=["active-focus"],
            )

        if signal == MemorySignal.verified_status_candidate:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="verified_status_candidate",
                confidence=0.55 if proof_present else 0.4,
                tags=["verified", "candidate", "proof-required"],
                proof_required=True,
            )

        if signal == MemorySignal.temporary_context:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="temporary_context",
                confidence=0.0,
            )

        if signal == MemorySignal.emotional_feedback_unclear:
            return MemoryCandidate(
                signal=signal,
                content=MemoryAutoPilotService._clean_message(message),
                memory_type="temporary_context",
                confidence=0.0,
            )

        return None

    @staticmethod
    def _classify_signal(normalized: str) -> MemorySignal:
        if not normalized:
            return MemorySignal.no_memory

        if normalized.startswith("remember this:") or normalized.startswith(
            "remember this "
        ):
            return MemorySignal.no_memory

        if (
            normalized.startswith("correction:")
            or "remember this workflow correction" in normalized
        ):
            return MemorySignal.no_memory

        if normalized.startswith("going forward"):
            return MemorySignal.no_memory

        if "code artifact" in normalized or "previewable true" in normalized:
            return MemorySignal.no_memory

        if any(
            token in normalized
            for token in (
                "operator mode",
                "proof project",
                "build and push",
                "push for real",
                "create a new repository",
                "check the repo",
                "push to github",
                "commit it",
                "commit to github",
                "initialize the new repository",
                "create a website in the repo",
            )
        ):
            return MemorySignal.no_memory

        if normalized.endswith("?"):
            return MemorySignal.no_memory

        if normalized.startswith(
            ("no, that is wrong", "no that is wrong", "that's not what i meant")
        ):
            if len(normalized.split()) <= 4:
                return MemorySignal.emotional_feedback_unclear
            return MemorySignal.user_correction

        if MemoryAutoPilotService.PROTECTED_PATTERN.search(normalized):
            return MemorySignal.no_memory

        if MemoryAutoPilotService.ACTIVE_FOCUS_PATTERN.search(normalized):
            return MemorySignal.active_focus_candidate

        if "preview first" in normalized and (
            "generate website" in normalized or "website" in normalized
        ):
            return MemorySignal.workflow_habit

        if MemoryAutoPilotService.ANSWER_STYLE_PATTERN.search(normalized):
            return MemorySignal.answer_style_preference

        if MemoryAutoPilotService.COMMUNICATION_PATTERN.search(normalized):
            return MemorySignal.communication_preference

        if MemoryAutoPilotService.WORKFLOW_PATTERN.search(normalized):
            return MemorySignal.workflow_habit

        if MemoryAutoPilotService.CORRECTION_PATTERN.search(normalized):
            if len(normalized.split()) <= 8:
                return MemorySignal.emotional_feedback_unclear
            return MemorySignal.user_correction

        if MemoryAutoPilotService.VERIFIED_PATTERN.search(normalized):
            return MemorySignal.verified_status_candidate

        if MemoryAutoPilotService.TEMPORARY_PATTERN.search(normalized):
            return MemorySignal.temporary_context

        if any(
            token in normalized
            for token in ("repo", "branch", "workspace", "project", "status")
        ):
            return MemorySignal.project_fact

        return MemorySignal.no_memory

    @staticmethod
    def _has_proof_metadata(session_metadata: dict[str, Any]) -> bool:
        if bool(session_metadata.get("live_repo_check")):
            return True
        last_action = session_metadata.get("operator_last_action")
        if isinstance(last_action, dict):
            if str(last_action.get("status", "")).lower() == "success":
                data = last_action.get("data")
                if isinstance(data, dict) and bool(data):
                    return True
        tool_results = session_metadata.get("tool_results")
        if isinstance(tool_results, list):
            for item in tool_results:
                if (
                    isinstance(item, dict)
                    and str(item.get("type", "")).lower() == "repo_check"
                ):
                    return True
        proof = session_metadata.get("proof_metadata")
        return isinstance(proof, dict) and bool(proof)

    @staticmethod
    def _active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
        focus_payload = session_metadata.get("active_focus")
        if isinstance(focus_payload, dict):
            summary = str(focus_payload.get("summary", "")).strip()
            if summary:
                return summary
        if isinstance(focus_payload, str):
            summary = focus_payload.strip()
            if summary:
                return summary
        return None

    @staticmethod
    def _clean_message(message: str) -> str:
        return " ".join(str(message or "").strip().split())

    @staticmethod
    def _build_receipt_text(records: list[MemoryRecord]) -> str:
        if not records:
            return "Context receipt: Memory none (active=0)."
        joined = ", ".join(record.id for record in records)
        return f"Context receipt: Memory {joined} (active={len(records)})."

    @staticmethod
    def _build_hints(message: str, records: list[MemoryRecord]) -> dict[str, Any]:
        lower_message = message.lower()
        lower_content = " ".join(record.content.lower() for record in records)
        hints: dict[str, Any] = {}
        if "preview first" in lower_content or "preview first" in lower_message:
            hints["preview_first"] = True
        if any(
            token in lower_content
            for token in (
                "don't guess",
                "do not guess",
                "verify repo status first",
                "proof first",
            )
        ):
            hints["require_proof"] = True
        if any(
            token in lower_content
            for token in ("be direct", "short answers", "keep it short", "unless i ask")
        ):
            hints["answer_style"] = "concise"
        return hints
