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

        if normalized in {"who are you?", "who are you"}:
            return [BrainLayer.SYSTEM_PROMPT]

        if normalized in {"what are we working on?", "what are we working on"}:
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
