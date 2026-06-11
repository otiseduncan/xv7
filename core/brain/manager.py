from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from core.brain.answer_contract import AnswerContract
from core.brain.context import BrainContext, BrainContextAssembler
from core.brain.records import BrainRecordLoader
from core.brain.schema import BrainLayer, BrainRecord


class BrainContextManager:
    """Facade for loading active records and assembling runtime context."""

    def __init__(self, records_dir: Path | None = None) -> None:
        self.loader = BrainRecordLoader(records_dir=records_dir)
        self.assembler = BrainContextAssembler()
        self.answer_contract = AnswerContract()

    def build_active_context(self) -> BrainContext:
        records = self.loader.load_active_records()
        return self.assembler.assemble(records)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.lower().strip().split())

    @staticmethod
    def _highest_priority_by_layer(records: list[BrainRecord]) -> dict[BrainLayer, BrainRecord]:
        result: dict[BrainLayer, BrainRecord] = {}
        for record in records:
            current = result.get(record.layer)
            if current is None or record.priority > current.priority:
                result[record.layer] = record
        return result

    def select_relevant_layers(self, question: str) -> list[BrainLayer]:
        normalized = self._normalize_question(question)

        if normalized in {
            "who are you?",
            "who are you",
            "what is your name?",
            "what is your name",
            "how do you pronounce your name?",
            "how do you pronounce your name",
            "how is your name pronounced?",
            "how is your name pronounced",
            "how do you spell your name?",
            "how do you spell your name",
            "how is your name spelled?",
            "how is your name spelled",
            "what does xv7 mean?",
            "what does xv7 mean",
            "what project are you?",
            "what project are you",
            "what project are you part of?",
            "what project are you part of",
            "is your name spelled exodus?",
            "is your name spelled exodus",
            "is your name spelled e-x-o-d-u-s?",
            "is your name spelled e-x-o-d-u-s",
        }:
            return [BrainLayer.SYSTEM_PROMPT]

        if normalized in {
            "who created you?",
            "who created you",
            "why were you built?",
            "why were you built",
            "what is your purpose?",
            "what is your purpose",
        }:
            return [BrainLayer.KNOWLEDGE]

        if normalized in {"who is otis?", "who is otis"}:
            return [BrainLayer.MEMORY]

        if normalized in {"what are we working on?", "what are we working on"}:
            return [BrainLayer.ACTIVE_FOCUS]

        if normalized in {
            "what are we working on right now?",
            "what are we working on right now",
        }:
            return [BrainLayer.ACTIVE_FOCUS]

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
            "what repo/status are we on?",
            "what repo/status are we on",
            "what failed?",
            "what failed",
            "did you check the repo?",
            "did you check the repo",
            "what model was proven during operator readiness?",
            "what model was proven during operator readiness",
        }:
            return [BrainLayer.VERIFIED_STATUS]

        if normalized in {"what do you remember?", "what do you remember"}:
            return [BrainLayer.MEMORY]

        if normalized in {
            "what do you remember about me?",
            "what do you remember about me",
            "what do you remember about xv7?",
            "what do you remember about xv7",
            "what do you remember about my preferences?",
            "what do you remember about my preferences",
            "is that memory, knowledge, or verified status?",
            "is that memory, knowledge, or verified status",
            "is that memory verified or just remembered?",
            "is that memory verified or remembered?",
            "is that verified or just remembered?",
            "is that verified or remembered?",
            "are launch proofs memory?",
            "are launch proofs memory",
            "what is my name?",
            "what is my name",
        }:
            return [BrainLayer.MEMORY]

        if normalized.startswith("search memory for"):
            return [BrainLayer.MEMORY]

        if normalized.startswith("remember this"):
            return [BrainLayer.MEMORY]

        if normalized.startswith("forget "):
            return [BrainLayer.MEMORY]

        if normalized.startswith("update "):
            return [BrainLayer.MEMORY]

        if normalized.startswith("approve the pending"):
            return [BrainLayer.MEMORY]

        if normalized in {
            "do you have any pending memories?",
            "do you have any pending memories",
            "what pending memory is waiting for approval?",
            "what pending memory is waiting for approval",
            "what active memories do you have now?",
            "what active memories do you have now",
            "is that memory active yet?",
            "is that memory active yet",
            "show the receipt memory status.",
            "show the receipt memory status",
            "did you delete the old receipt memory or supersede it?",
            "did you delete the old receipt memory or supersede it",
            "what memory records shaped that answer?",
            "what memory records shaped that answer",
        }:
            return [BrainLayer.MEMORY]

        if normalized in {
            "what do you know about xv7 architecture?",
            "what do you know about xv7 architecture",
            "answer from knowledge only: what is xv7’s architecture?",
            "answer from knowledge only: what is xv7's architecture?",
            "answer from knowledge only: what is xv7 architecture?",
            "if we are planning an app, can you help me do that?",
            "if we are planning an app, can you help me do that",
            "can you help design the architecture?",
            "can you help design the architecture",
            "can you help write implementation prompts for vs code/copilot?",
            "can you help write implementation prompts for vs code/copilot",
            "write a vs code prompt for b8.2",
            "do you have a microphone button?",
            "do you have a microphone button",
            "does the mic auto-send?",
            "does the mic auto-send",
            "do you have copy chat?",
            "do you have copy chat",
            "can i copy individual prompts?",
            "can i copy individual prompts",
            "what color theme are we using?",
            "what color theme are we using",
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return [BrainLayer.KNOWLEDGE]

        if normalized in {
            "answer from verified status only: what is proven?",
            "answer from verified status only: what is proven",
        }:
            return [BrainLayer.VERIFIED_STATUS]

        if normalized in {"are we beta ready?", "are we beta ready"}:
            return [BrainLayer.VERIFIED_STATUS, BrainLayer.ACTIVE_FOCUS]

        if normalized in {"what model are you using?", "what model are you using"}:
            return [BrainLayer.SYSTEM_PROMPT]

        if "guess" in normalized:
            return [BrainLayer.ACTIVE_FOCUS]

        layers: list[BrainLayer] = [BrainLayer.SYSTEM_PROMPT]
        if re.search(r"\b(work|working|focus|task|priority)\b", normalized):
            layers.append(BrainLayer.ACTIVE_FOCUS)
        if re.search(r"\b(verified|prove|proof|repo|branch|status|sync|synced)\b", normalized):
            layers.append(BrainLayer.VERIFIED_STATUS)
        if re.search(r"\b(remember|memory|prefer|preference|asked|request)\b", normalized):
            layers.append(BrainLayer.MEMORY)
        if re.search(r"\b(architecture|component|service|system|how)\b", normalized):
            layers.append(BrainLayer.KNOWLEDGE)

        if layers == [BrainLayer.SYSTEM_PROMPT]:
            layers.append(BrainLayer.KNOWLEDGE)

        deduped: list[BrainLayer] = []
        for layer in layers:
            if layer not in deduped:
                deduped.append(layer)
        return deduped

    def build_context_for_question(self, question: str) -> BrainContext:
        records = self.loader.load_active_records()
        layer_map = self._highest_priority_by_layer(records)
        selected_layers = self.select_relevant_layers(question)
        selected_records = [
            layer_map[layer] for layer in selected_layers if layer in layer_map
        ]
        return self.assembler.assemble(
            selected_records,
            target_layers=selected_layers,
        )

    def answer_from_records(
        self,
        question: str,
        *,
        session_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Return policy-controlled answers for quality-critical prompts."""
        records = self.loader.load_active_records()

        layer_map = self._highest_priority_by_layer(records)
        return self.answer_contract.try_answer(
            question,
            records_by_layer=layer_map,
            session_metadata=session_metadata or {},
        )
